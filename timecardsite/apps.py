from django.apps import AppConfig

class TimecardsiteConfig(AppConfig):
    name = 'timecardsite'

    def ready(self):
        import timecardsite.signals
