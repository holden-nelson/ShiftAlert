from datetime import timedelta, date

class WeeklyPayPeriod():
    def __init__(self, dow):
        self.dow = dow

    def _weekly(self, given_date):
        beginning = given_date - timedelta(days=((given_date.weekday() - self.dow) % 7))
        end = beginning + timedelta(days=6)

        return (beginning, end)

    def get(self, given_date):
        return self._weekly(given_date)

    def current(self):
        return self._weekly(date.today())

    def previous(self):
        return self._weekly(date.today() - timedelta(weeks=1))

class BiWeeklyPayPeriod():
    def __init__(self, reference_date):
        # reference_date is a user supplied first day of pay period
        self.dow = reference_date.weekday()
        self.reference_date = reference_date

    def _within_two_week_multiple(self, given_date):
        # is the given date 2x weeks before or after reference date, for any x
        difference = given_date - self.reference_date
        return difference.days % 14 == 0

    def _biweekly(self, given_date):
        beginning = given_date - timedelta(days=((given_date.weekday() - self.dow) % 7))
        if not self._within_two_week_multiple(beginning):
            beginning -= timedelta(weeks=1)

        end = beginning + timedelta(days=13)

        return (beginning, end)

    def get(self, given_date):
        return self._biweekly(given_date)

    def current(self):
        return self._biweekly(date.today())

    def previous(self):
        return self._biweekly(date.today() - timedelta(weeks=2))