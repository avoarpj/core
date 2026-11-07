"""Explicit validation and lossless conversions for generated Protobuf messages."""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal as PythonDecimal, InvalidOperation

from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.message import Message
from google.protobuf.timestamp_pb2 import Timestamp

from avoar.core.opendata.common.domain import Date, Decimal
from avoar.core.opendata.common.options_pb2 import rules

_DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")


def _decimal(value: str) -> PythonDecimal:
    if not _DECIMAL.fullmatch(value):
        raise ValueError("expected a finite base-10 decimal string")
    try:
        return PythonDecimal(value)
    except InvalidOperation as error:
        raise ValueError("decimal exponent is out of range") from error


def decimal_value(value: str | int | PythonDecimal) -> Decimal:
    """Create a lossless decimal message. Floats are deliberately rejected."""
    if not isinstance(value, (str, int, PythonDecimal)) or isinstance(value, bool):
        raise TypeError("Use str, int or decimal.Decimal, not float")
    text = str(value)
    _decimal(text)
    return Decimal(value=text)


def date_value(value: date) -> Date:
    """Create a calendar date without implicitly discarding a time or timezone."""
    if not isinstance(value, date) or isinstance(value, datetime):
        raise TypeError("Use datetime.date")
    return Date(year=value.year, month=value.month, day=value.day)


def timestamp_value(value: datetime) -> Timestamp:
    """Create an instant; naive datetimes must first be assigned a timezone."""
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("Timestamp requires a timezone-aware datetime")
    message = Timestamp()
    message.FromDatetime(value)
    return message


def validate(message: Message) -> None:
    """Raise ValueError for missing required values or invalid domain values.

    Call after construction/deserialization and before publishing data. Protobuf
    constructors and SerializeToString do not execute semantic validation.
    """
    if not isinstance(message, Message):
        raise TypeError("Expected a Protobuf message")
    _validate(message, message.DESCRIPTOR.name)


def _validate(message: Message, path: str) -> None:
    for field in message.DESCRIPTOR.fields:
        constraint = field.GetOptions().Extensions[rules]
        field_path = f"{path}.{field.name}"
        if field.has_presence and not message.HasField(field.name):
            if constraint.required:
                raise ValueError(f"{field_path}: required field is absent")
            continue
        value = getattr(message, field.name)
        values = value if field.is_repeated else [value]
        for index, item in enumerate(values):
            item_path = f"{field_path}[{index}]" if field.is_repeated else field_path
            if field.type == FieldDescriptor.TYPE_MESSAGE:
                _validate(item, item_path)
            if field.type == FieldDescriptor.TYPE_ENUM:
                enum_value = field.enum_type.values_by_number.get(item)
                if enum_value is None or enum_value.name.endswith("_UNSPECIFIED"):
                    raise ValueError(f"{item_path}: unknown or unspecified enum value {item}")
            if constraint.allowed_values and item not in constraint.allowed_values:
                raise ValueError(f"{item_path}: expected one of {list(constraint.allowed_values)}")
            if constraint.HasField("minimum") or constraint.HasField("maximum"):
                is_decimal = (
                    field.message_type is not None
                    and field.message_type.full_name == "avoar.core.opendata.common.Decimal"
                )
                number = _decimal(item.value) if is_decimal else PythonDecimal(str(item))
                if not number.is_finite():
                    raise ValueError(f"{item_path}: expected a finite number")
                if constraint.HasField("minimum") and number < PythonDecimal(constraint.minimum):
                    raise ValueError(f"{item_path}: below minimum {constraint.minimum}")
                if constraint.HasField("maximum") and number > PythonDecimal(constraint.maximum):
                    raise ValueError(f"{item_path}: above maximum {constraint.maximum}")
    name = message.DESCRIPTOR.full_name
    try:
        if name == "avoar.core.opendata.common.Decimal":
            _decimal(message.value)
        elif name == "avoar.core.opendata.common.Date":
            date(message.year, message.month, message.day)
        elif name == "google.protobuf.Timestamp":
            # ToJsonString checks both the seconds and nanoseconds ranges.
            message.ToJsonString()
    except (ValueError, OverflowError) as error:
        raise ValueError(f"{path}: {error}") from error
