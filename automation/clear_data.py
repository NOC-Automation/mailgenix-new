# how to run:
# python manage.py shell < clear_data.py

import random
from datetime import date, timedelta

from core.models import (
    Customers,
    FloorLevel,
    Rack,
    AR,
    ARGroup,
    MailingList,
    SiteLocation,
    EmailLogs
)

print("🔄 Cleaning existing data...")

AR.objects.all().delete()
ARGroup.objects.all().delete()
MailingList.objects.all().delete()
Customers.objects.all().delete()
Rack.objects.all().delete()
FloorLevel.objects.all().delete()
SiteLocation.objects.all().delete()
EmailLogs.objects.all().delete()
