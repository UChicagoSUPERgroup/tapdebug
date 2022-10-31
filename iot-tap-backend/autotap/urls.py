from django.urls import path

from . import views

urlpatterns = [
    path('fix/', views.fix, name='fix'),
    path('suggestadd/', views.suggestadd, name='suggestadd'),
    path('suggestdebug/', views.suggestdebug, name='suggestdebug'),
    path('getepisode/', views.getepisode, name='getepisode'),
    path('getepisodedebug/', views.getepisode_debug, name='getepisodedebug'),
    path('getepisodemanual/', views.getepisode_manual, name='getepisodemanual'),
    path('getepisodeformanualfeedback/', views.getepisode_feedback, name='getepisodeformanualfeedback'),
    path('sendfeedback/', views.send_feedback, name='sendfeedback'),
    path('getrulesforsyntax/', views.get_rules_for_syntax, name='getrulesforsyntax'),
    path('revert/loc/', views.get_revert_for_location, name="getrevertforloc"),
    path('revert/action/', views.get_revert_action, name="getrevertaction"),
    path('manual/', views.get_manual_changes, name="getmanualchange"),
    path('debugpage/', views.get_debug_pages, name="getdebugpages")
]
