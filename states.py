# ---------- State Pattern ----------
# Donation behavior changes according to its current lifecycle state.
class DonationState:
    name = 'UNKNOWN'

    def reserve(self):
        raise ValueError(f'{self.name} donations cannot be reserved')

    def complete(self):
        raise ValueError(f'{self.name} donations cannot be completed')

    def expire(self):
        raise ValueError(f'{self.name} donations cannot be expired')


class AvailableState(DonationState):
    name = 'AVAILABLE'

    def reserve(self):
        return ReservedState()

    def expire(self):
        return ExpiredState()


class ReservedState(DonationState):
    name = 'RESERVED'

    def complete(self):
        return CompletedState()

    def expire(self):
        return ExpiredState()


class CompletedState(DonationState):
    name = 'COMPLETED'


class ExpiredState(DonationState):
    name = 'EXPIRED'


# ---------- Factory Pattern ----------
# Centralizes creation of the correct State object from the stored status.
class DonationStateFactory:
    _state_types = {
        'AVAILABLE': AvailableState,
        'RESERVED': ReservedState,
        'COMPLETED': CompletedState,
        'EXPIRED': ExpiredState,
    }

    @classmethod
    def create_state(cls, status: str) -> DonationState:
        state_class = cls._state_types.get(status.upper())
        if state_class is None:
            raise ValueError(f'Unknown donation status: {status}')
        return state_class()
