# -*- coding: utf-8 -*-
#
# Copyright (C) 2022 CERN.
#
# Invenio-RDM-Migrator is free software; you can redistribute it and/or modify
# it under the terms of the MIT License; see LICENSE file for more details.

"""Invenio RDM migration record table load module."""


import random
import uuid
from datetime import datetime

from ...load.models import PersistentIdentifier
from ...load.postgresql import TableGenerator
from .models import RDMParentMetadata, RDMRecordMetadata, RDMVersionState


class RDMVersionStateComputedTable(TableGenerator):
    """RDM version state computed table."""

    def __init__(self, parent_cache):
        """Constructor."""
        super().__init__(tables=[RDMVersionState])
        self.parent_cache = parent_cache

    def _generate_rows(self, **kwargs):
        for parent_state in self.parent_cache.values():
            # Version state to be populated in the end from the final state
            yield RDMVersionState(
                latest_index=parent_state["version"]["latest_index"],
                parent_id=parent_state["id"],
                latest_id=parent_state["version"]["latest_id"],
                next_draft_id=None,
            )


# keep track of generated PKs, since there's a chance they collide
GENERATED_PID_PKS = set()


def _pid_pk():
    while True:
        # we start at 1M to avoid collisions with existing low-numbered PKs
        val = random.randint(1_000_000, 2_147_483_647 - 1)
        if val not in GENERATED_PID_PKS:
            GENERATED_PID_PKS.add(val)
            return val


def _generate_recid(data):
    return {
        "pk": _pid_pk(),
        "obj_type": "rec",
        "pid_type": "recid",
        "status": "R",
    }


def _generate_uuid(data):
    return str(uuid.uuid4())


class RDMRecordTableLoad(TableGenerator):
    """RDM Record and related tables load."""

    def __init__(self, parent_cache):
        """Constructor."""
        super().__init__(
            tables=[
                PersistentIdentifier,
                RDMParentMetadata,
                RDMRecordMetadata,
            ],
            pks=[
                ("record.id", _generate_uuid),
                ("parent.id", _generate_uuid),
                ("record.json.pid", _generate_recid),
                ("parent.json.pid", _generate_recid),
                ("record.parent_id", lambda d: d["parent"]["id"]),
            ],
        )
        self.parent_cache = parent_cache

    def _generate_rows(self, data, **kwargs):
        now = datetime.utcnow().isoformat()

        # record
        rec = data["record"]
        record_pid = rec["json"]["pid"]
        parent = data["parent"]
        rec_parent_id = self.parent_cache.get(parent["json"]["id"], {}).get("id")
        yield RDMRecordMetadata(
            id=rec["id"],
            json=rec["json"],
            created=rec["created"],
            updated=rec["updated"],
            version_id=rec["version_id"],
            index=rec["index"],
            bucket_id=rec.get("bucket_id"),
            parent_id=rec_parent_id or rec["parent_id"],
        )
        # recid
        yield PersistentIdentifier(
            id=record_pid["pk"],
            pid_type=record_pid["pid_type"],
            pid_value=rec["json"]["id"],
            status=record_pid["status"],
            object_type=record_pid["obj_type"],
            object_uuid=rec["id"],
            created=now,
            updated=now,
        )
        # DOI
        if "doi" in rec["json"]["pids"]:
            yield PersistentIdentifier(
                id=_pid_pk(),
                pid_type="doi",
                pid_value=rec["json"]["pids"]["doi"]["identifier"],
                status="R",
                object_type="rec",
                object_uuid=rec["id"],
                created=now,
                updated=now,
            )
        # OAI
        yield PersistentIdentifier(
            id=_pid_pk(),
            pid_type="oai",
            pid_value=rec["json"]["pids"]["oai"]["identifier"],
            status="R",
            object_type="rec",
            object_uuid=rec["id"],
            created=now,
            updated=now,
        )

        # parent
        if parent["json"]["id"] not in self.parent_cache:
            self.parent_cache[parent["json"]["id"]] = dict(
                id=parent["id"],
                version=dict(latest_index=rec["index"], latest_id=rec["id"]),
            )
            parent_pid = parent["json"]["pid"]
            # record
            yield RDMParentMetadata(
                id=parent["id"],
                json=parent["json"],
                created=parent["created"],
                updated=parent["updated"],
                version_id=parent["version_id"],
            )
            # recid
            yield PersistentIdentifier(
                id=parent_pid["pk"],
                pid_type=parent_pid["pid_type"],
                pid_value=parent["json"]["id"],
                status=parent_pid["status"],
                object_type=parent_pid["obj_type"],
                object_uuid=parent["id"],
                created=now,
                updated=now,
            )
        else:
            # parent in cache - update version
            cached_parent = self.parent_cache[parent["json"]["id"]]
            # check if current record is a new version of the cached one
            if cached_parent["version"]["latest_index"] < rec["index"]:
                cached_parent["version"] = dict(
                    latest_index=rec["index"], latest_id=rec["id"]
                )
