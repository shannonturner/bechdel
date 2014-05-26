from django.conf.urls import patterns, include, url

from django.contrib import admin
admin.autodiscover()

from apps.bechdel.views import HomeView, SearchView, MovieView, AllMovies

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'bechdel.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

    # url(r'^admin/', include(admin.site.urls)),
    url(r'^(?:bechdel/)?$', HomeView.as_view(), name='home'),
    url(r'^(?:bechdel/)?search$', SearchView.as_view(), name='search'),
    url(r'^(?:bechdel/)?movie/(?P<id>[0-9]+)$', MovieView.as_view(), name='movie'),
    url(r'^(?:bechdel/)?movie$', AllMovies.as_view(), name='all_movies')
)
