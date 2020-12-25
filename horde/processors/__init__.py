from typing import Type

from .endorser import EndorserProcessor
from .router import Router
from .orderer import OrdererProcessor


# pylint:disable=inconsistent-return-statements
def processor_factory(node_type: str) -> Type[Router]:
    if node_type == 'orderer':
        return OrdererProcessor
    if node_type == 'endorser':
        return EndorserProcessor
    assert False, 'unknown node type'
