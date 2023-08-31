# -*- coding: utf-8 -*-
#
# Copyright (C) 2023 CERN.
#
# Invenio-RDM-Migrator is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.

"""Invenio RDM migration PostgreSQL models module."""

from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass
from sqlalchemy.types import JSON


class Model(MappedAsDataclass, DeclarativeBase):
    """subclasses will be converted to dataclasses."""

    type_annotation_map = {
        dict: JSON,
    }
