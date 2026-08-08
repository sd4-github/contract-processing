from django.contrib import admin
from .models import Batch, ContractDocument, Finding

admin.site.register([Batch, ContractDocument, Finding])

