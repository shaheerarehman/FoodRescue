from states import (
    DonationStateFactory,
    AvailableState,
    ReservedState,
    CompletedState,
    ExpiredState,
)


def test_factory_creates_available_state():
    state = DonationStateFactory.create_state("AVAILABLE")
    assert isinstance(state, AvailableState)


def test_factory_creates_reserved_state():
    state = DonationStateFactory.create_state("RESERVED")
    assert isinstance(state, ReservedState)


def test_available_can_be_reserved():
    state = AvailableState()
    new_state = state.reserve()

    assert isinstance(new_state, ReservedState)


def test_reserved_can_be_completed():
    state = ReservedState()
    new_state = state.complete()

    assert isinstance(new_state, CompletedState)


def test_available_can_expire():
    state = AvailableState()
    new_state = state.expire()

    assert isinstance(new_state, ExpiredState)