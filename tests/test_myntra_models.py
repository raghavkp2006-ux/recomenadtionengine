from models.base import Base
from models.myntra import MyntraConnection, MyntraEvent, MyntraFeedback, MyntraProduct, MyntraProfile


def test_myntra_models_are_registered_on_the_application_base():
    tables = Base.metadata.tables

    assert MyntraEvent.__tablename__ in tables
    assert MyntraProduct.__tablename__ in tables
    assert MyntraProfile.__tablename__ in tables
    assert MyntraFeedback.__tablename__ in tables
    assert MyntraConnection.__tablename__ in tables


def test_myntra_event_id_and_product_identity_are_unique():
    event_constraints = [constraint for constraint in MyntraEvent.__table__.constraints if constraint.name]
    product_constraints = [constraint for constraint in MyntraProduct.__table__.constraints if constraint.name]

    assert any(constraint.name == "uq_myntra_product_id" for constraint in product_constraints)
    assert MyntraEvent.__table__.c.event_id.unique is True
