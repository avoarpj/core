# Avoar Core

O Avoar Core é a base aberta de contratos de dados do Avoar, projeto que trabalha
com dados públicos brasileiros sobre eleições, representação política, recursos
públicos e empresas.

Este repositório define como essas informações são representadas e relacionadas.
Seus contratos oferecem uma referência comum para os componentes que produzem,
processam e consomem dados no ecossistema Avoar, além de poderem ser reutilizados
em outros projetos.

## O que você encontra aqui

Os contratos são escritos em **Protocol Buffers (Protobuf)**, permitindo gerar
modelos para diferentes linguagens a partir das mesmas definições.

| Área | Contratos |
| --- | --- |
| Eleições | Pleitos, eleições, candidaturas, urnas, boletins de urna e locais de votação |
| Representação política | Pessoas públicas, partidos, órgãos, legislaturas e mandatos |
| Recursos públicos | Emendas parlamentares, convênios, reembolsos da CEAP e fornecedores |
| Empresas e território | Empresas, estabelecimentos, sócios, municípios e endereços |

O core também reúne tipos compartilhados para datas e valores decimais, regras
de validação e documentação dos domínios. A geração de código está disponível
para **Python 3.12 ou superior**.

## Organização

Cada domínio possui sua própria pasta em [`avoar/core/opendata`](avoar/core/opendata),
com as mensagens e enums definidos em `domain.proto`.

```text
avoar/core/
  opendata/
    business/domain.proto
    election/domain.proto
    mandate/domain.proto
    municipality/domain.proto
    ...
    common/
      domain.proto       # tipos compartilhados
      options.proto      # regras de validação
  common/                # utilitários Python
  validation.py          # validação e conversões Python
```

As referências entre entidades permitem relacionar informações de diferentes
domínios, como uma candidatura à pessoa pública e à eleição correspondentes,
ou um mandato à sua legislatura e ao órgão associado.

## Uso em Python

Adicione o core ao seu projeto com `uv`:

```bash
uv add 'git+https://github.com/avoarpj/core.git'
```

Os módulos Python são gerados durante a instalação e disponibilizados no ambiente,
com imports organizados por domínio:

```python
from avoar.core.opendata.municipality.domain import Municipio
from avoar.core.validation import decimal_value, validate

municipio = Municipio(
    codigo_ibge="3550308",
    nome="São Paulo",
    nome_normalizado="sao paulo",
    uf="SP",
    latitude=decimal_value("-23.550520"),
    longitude=decimal_value("-46.633308"),
)
validate(municipio)
```

Os objetos usam a API nativa do Protobuf para serialização e leitura de dados.
A validação de domínio é explícita: execute `validate` após construir ou
desserializar uma mensagem. Valores decimais são representados sem conversão
por ponto flutuante, e campos opcionais permitem consultar a presença do valor.

## Desenvolvimento

Para preparar o ambiente a partir de um clone deste repositório:

```bash
uv sync
uv run python -m unittest discover -s tests -v
```

Edite os arquivos `.proto` e execute `uv sync` para atualizar os contratos
instalados. A geração usa uma pasta temporária e mantém os arquivos resultantes
no ambiente Python, separados dos contratos-fonte.

Para inspecionar a geração manualmente em `build/python/` e depois limpá-la:

```bash
uv run python scripts/generate_python.py
python scripts/generate_python.py --clean
```

Ao alterar contratos, preserve os números dos campos e dos enums existentes.
Reserve nomes e números removidos com `reserved` para manter a compatibilidade
dos dados entre versões.

## Licença

Disponível sob a [Unlicense](LICENSE).
