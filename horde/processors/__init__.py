from typing import Type

from .admin import AdminProcessor
from .client import ClientProcessor
from .endorser import EndorserProcessor
from .orderer import OrdererProcessor
from .router import Router


# pylint:disable=inconsistent-return-statements
def processor_factory(node_type: str) -> Type[Router]:
    if node_type == 'orderer':
        return OrdererProcessor
    if node_type == 'endorser':
        return EndorserProcessor
    if node_type == 'client':
        return ClientProcessor
    if node_type == 'admin':
        return AdminProcessor
    assert False, 'unknown node type'
