"""backend URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings

import backend.views as v


urlpatterns = [
    path('backend/admin/',admin.site.urls),
    path('backend/user/login/', v.fe_login),
    path('backend/user/logout/', v.fe_logout),
    path('backend/user/get_loc_token/', v.fe_get_loc_token),
    path('backend/user/get/',v.fe_get_user),
    path('backend/user/devices/', v.fe_get_devices),
    path('backend/user/loc/rules/',v.fe_all_rules),
    path('backend/user/chans/',v.fe_all_chans),
    path('backend/user/zones/', v.fe_all_zones),
    path('backend/user/chans/devs/',v.fe_devs_with_chan),
    path('backend/user/chans/devs/caps/',v.fe_get_valid_caps),
    path('backend/user/chans/devs/caps/params/',v.fe_get_params),
    path('backend/user/loc/devs/', v.fe_devs_with_loc),
    path('backend/user/loc/devs/caps/', v.fe_get_valid_caps_with_loc),
    path('backend/user/rules/new/',v.fe_create_esrule),
    path('backend/user/rules/newbatch/', v.fe_create_esrules),
    path('backend/user/rules/changebatch/', v.fe_change_esrules),
    path('backend/user/rules/delete/',v.fe_delete_rule),
    path('backend/user/rules/get/',v.fe_get_full_rule),
    path('backend/user/sps/',v.fe_all_sps),
    path('backend/user/sp1/new/',v.fe_create_sp1),
    path('backend/user/sp2/new/',v.fe_create_sp2),
    path('backend/user/sp3/new/',v.fe_create_sp3),
    path('backend/user/sps/delete/',v.fe_delete_sp),
    path('backend/user/sps/get/',v.fe_get_full_sp),
    path('backend/user/sp1/get/',v.fe_get_full_sp1),
    path('backend/user/sp2/get/',v.fe_get_full_sp2),
    path('backend/user/sp3/get/',v.fe_get_full_sp3),
    path('backend/user/get_cookie/', v.fe_get_cookie),
    path('backend/user/getmonitoreddevstatus/', v.fe_get_monitored_dev_status),
    path('backend/user/getscenarioinfo/', v.fe_get_scenario_info),
    path('backend/user/upload_trace/', v.fe_upload_trace),
    path('backend/autotap/', include('autotap.urls')),
    path('backend/homeio/rules/', v.hio_all_rules),
    path('backend/homeio/upload_trace/', v.hio_upload_trace),
    path('backend/homeio/get_monitored_devs/', v.hio_get_monitored_devs),
    path('backend/homeio/get_rules_and_devs/', v.hio_get_rules_and_devs),
    path('backend/homeio/update_monitored_devs/', v.hio_update_monitored_devs),
]
