import importlib
import math
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal as PythonDecimal
from pathlib import Path

from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.message import Message
from google.protobuf.timestamp_pb2 import Timestamp

from avoar.core.opendata.business.domain import Empresa, TipoEstabelecimento
from avoar.core.opendata.common.domain import Date, Decimal, StringList
from avoar.core.opendata.election.domain import TipoEleicao
from avoar.core.opendata.mandate.domain import GabineteMandato
from avoar.core.opendata.municipality.domain import Municipio
from avoar.core.opendata.pleito.domain import Pleito
from avoar.core.opendata.public_people.domain import PessoaPublica
from avoar.core.opendata.voting_location.domain import LocalVotacao
from avoar.core.validation import date_value, decimal_value, timestamp_value, validate


class ContractTests(unittest.TestCase):
    def empresa(self):
        return Empresa(
            id=2**64 - 1,
            base_cnpj="00123456",
            razao_social="Avoar",
            natureza_juridica=1,
            qualificacao_responsavel=1,
            capital_social=decimal_value("12345678901234567890.123456789"),
        )

    def municipio(self):
        return Municipio(
            codigo_ibge="3550308", nome="São Paulo", nome_normalizado="sao paulo",
            uf="SP", latitude=decimal_value("-23.550520"), longitude=decimal_value("-46.633308"),
        )

    def test_public_imports_for_every_domain(self):
        import avoar.core.opendata as opendata
        for schema in Path(next(iter(opendata.__path__))).glob("*/domain.proto"):
            module = "avoar.core.opendata." + schema.parent.name
            with self.subTest(module=module):
                public = importlib.import_module(module)
                domain = importlib.import_module(module + ".domain")
                generated = importlib.import_module(module + ".domain_pb2")
                for name, descriptor in generated.DESCRIPTOR.message_types_by_name.items():
                    self.assertIs(getattr(public, name), getattr(domain, name))
                    self.assertEqual(getattr(domain, name).DESCRIPTOR, descriptor)
                    self.assertIsInstance(getattr(domain, name)(), Message)

    def test_uint64_and_decimal_binary_and_json_roundtrip(self):
        original = self.empresa()
        validate(original)
        restored = Empresa.FromString(original.SerializeToString())
        self.assertEqual(restored, original)
        self.assertEqual(restored.id, 2**64 - 1)
        payload = MessageToDict(original)
        self.assertEqual(payload["id"], str(2**64 - 1))
        self.assertEqual(payload["capitalSocial"]["value"], "12345678901234567890.123456789")
        self.assertEqual(ParseDict(payload, Empresa()), original)
        for invalid in (-1, 2**64):
            with self.assertRaises(ValueError):
                Empresa(id=invalid)

    def test_missing_required_field_and_explicit_zero(self):
        company = self.empresa()
        company.ClearField("id")
        with self.assertRaisesRegex(ValueError, "Empresa.id"):
            validate(company)
        company.id = 0
        validate(company)

    def test_optional_scalar_presence_survives_roundtrip(self):
        company = self.empresa()
        self.assertFalse(company.HasField("porte"))
        company.porte = 0
        restored = Empresa.FromString(company.SerializeToString())
        self.assertTrue(restored.HasField("porte"))
        self.assertEqual(restored.porte, 0)
        restored.ClearField("porte")
        self.assertFalse(restored.HasField("porte"))

    def test_nullable_list_distinguishes_absent_and_empty(self):
        office = GabineteMandato(mandato_id=0)
        self.assertFalse(office.HasField("telefones"))
        office.telefones.CopyFrom(StringList())
        restored = GabineteMandato.FromString(office.SerializeToString())
        self.assertTrue(restored.HasField("telefones"))
        self.assertEqual(list(restored.telefones.values), [])
        restored.telefones.values.append("1234")
        self.assertEqual(list(restored.telefones.values), ["1234"])

    def test_decimal_and_float_coordinate_constraints(self):
        city = self.municipio()
        validate(city)
        city.latitude.CopyFrom(decimal_value("90.0000000000000000001"))
        with self.assertRaisesRegex(ValueError, "Municipio.latitude"):
            validate(city)
        city.latitude.CopyFrom(decimal_value("90"))
        city.longitude.CopyFrom(decimal_value("-180"))
        validate(city)
        location = LocalVotacao(
            id=0, uf="SP", codigo_municipio_tse="1", zona_eleitoral="1", numero="1",
            ano_referencia=2026, data_eleicao=date_value(date(2026, 10, 4)), numero_turno=1,
        )
        for invalid in (math.nan, math.inf, -91):
            location.latitude_tse = invalid
            with self.assertRaisesRegex(ValueError, "latitude_tse"):
                validate(location)

    def test_decimal_rejects_nonfinite_and_imprecise_inputs(self):
        for invalid in ("NaN", "Infinity", "1_000", "", "1,23"):
            with self.assertRaises(ValueError):
                validate(Decimal(value=invalid))
        with self.assertRaises(TypeError):
            decimal_value(0.1)
        self.assertEqual(decimal_value(PythonDecimal("0.100")).value, "0.100")

    def test_calendar_date_and_timestamp(self):
        election = Pleito(id=0, ano=2024, tipo=TipoEleicao.ORDINARIA, data_inicio=date_value(date(2024, 2, 29)))
        validate(election)
        election.data_inicio.year = 2023
        with self.assertRaisesRegex(ValueError, "Pleito.data_inicio"):
            validate(election)
        for invalid in (Date(year=2024, month=0, day=1), Date(year=2024, month=1)):
            with self.assertRaises(ValueError):
                validate(invalid)
        instant = datetime(2026, 11, 7, 12, 30, tzinfo=timezone.utc)
        self.assertEqual(timestamp_value(instant).ToDatetime(timezone.utc), instant)
        with self.assertRaises(ValueError):
            timestamp_value(instant.replace(tzinfo=None))
        with self.assertRaises(ValueError):
            validate(Timestamp(seconds=0, nanos=1_000_000_000))

    def test_enum_members_and_imported_enum(self):
        self.assertEqual(TipoEstabelecimento.MATRIZ.value, 1)
        self.assertEqual(TipoEleicao.ORDINARIA.value, 1)
        election = Pleito(id=0, ano=2026, tipo=TipoEleicao.ORDINARIA, data_inicio=date_value(date(2026, 10, 4)))
        validate(election)
        for invalid in (0, 999):
            election.tipo = invalid
            with self.assertRaisesRegex(ValueError, "Pleito.tipo"):
                validate(election)

    def test_literal_constraint(self):
        person = PessoaPublica(id=0, nome="Ana", nome_completo="Ana Silva", genero="F")
        validate(person)
        person.genero = "X"
        with self.assertRaisesRegex(ValueError, "PessoaPublica.genero"):
            validate(person)


if __name__ == "__main__":
    unittest.main()
