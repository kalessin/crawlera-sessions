"""
Decorator for callbacks that returns iterator of requests.
This decorator must be applied for every callback that yields requests that
must conserve session. For starting requests, use init_start_request.
In most use cases, each start request should have a different one.

You will also need to replace the default redirect middleware with the one provided here.

Example:


crawlera_session = RequestSession()


class MySpider(Spider):

    @classmethod
    def update_settings(cls, settings):
        super().update_settings(settings)
        pos = settings.get('DOWNLOADER_MIDDLEWARES_BASE').pop('scrapy.downloadermiddlewares.redirect.RedirectMiddleware')
        DW_MIDDLEWARES = settings.get('DOWNLOADER_MIDDLEWARES')
        DW_MIDDLEWARES['crawlera_session.CrawleraSessionRedirectMiddleware'] = pos

    @crawlera_session.init_start_requests
    def start_requests(self):
        ...
        yield Request(...)


    @crawlera_session.follow_session
    def parse(self, response):
        ...
        yield Request(...)


Some times you need to initialize a session for a single request generated in a spider method. In that case,
you can use init_request() method:

    def parse(self, response):
        ...
        yield Request(...)
        ...
        yield crawlera_session.init_request(Request(...))


If on the contrary, you want to send a normal (not session) request from a callback that was decorated with follow_session,
you can use the no_crawlera_session meta tag:

    @crawlera_session.follow_session
    def parse(self, response):
        ...
        yield Request(...)
        ...
        yield Request(..., meta={'no_crawlera_session': True})

"""
import uuid
import logging
from collections import OrderedDict

from scrapy import Request
from scrapy.downloadermiddlewares.redirect import RedirectMiddleware


__version__ = '1.1.0'

logger = logging.getLogger(__name__)


class RequestSession(object):
    def __init__(self, crawlera_session=True, x_crawlera_cookies='disable', x_crawlera_profile=None, x_crawlera_wait=None):
        self.crawlera_session = crawlera_session
        self.x_crawlera_cookies = x_crawlera_cookies
        self.x_crawlera_profile = x_crawlera_profile
        self.x_crawlera_wait = x_crawlera_wait

    def follow_session(self, wrapped):
        def _wrapper(spider, response, *args, **kwargs):
            if not hasattr(spider, 'crawlera_sessions'):
                spider.crawlera_sessions = OrderedDict()
            try:
                cookiejar = response.meta['cookiejar']
            except KeyError:
                cookiejars = list(spider.crawlera_sessions.keys())
                if cookiejars:
                    cookiejar = cookiejars[-1]  # use newest session by default
                else:
                    raise ValueError('You must initialize request.')
            for obj in wrapped(spider, response, *args, **kwargs):
                if isinstance(obj, Request) and not obj.meta.get('no_crawlera_session', False):
                    if self.crawlera_session and 'X-Crawlera-Session' not in obj.headers:
                        session = spider.crawlera_sessions.setdefault(cookiejar, response.headers['X-Crawlera-Session'])
                        logger.debug(f"Assigned session {session} to {obj} from cookiejar {cookiejar}")
                        obj.headers['X-Crawlera-Session'] = session
                    self._adapt_request(obj)
                    if 'cookiejar' not in obj.meta:
                        obj.meta['cookiejar'] = cookiejar
                yield obj
        # hack for conserving original callback name, for correct working of scrapy-frontera scheduler
        _wrapper.__name__ = wrapped.__name__
        return _wrapper

    def _adapt_request(self, request):
        if self.x_crawlera_cookies is not None:
            request.headers['X-Crawlera-Cookies'] = self.x_crawlera_cookies
        if self.x_crawlera_profile is not None:
            request.headers['X-Crawlera-Profile'] = self.x_crawlera_profile
        if self.x_crawlera_wait is not None:
            request.headers['X-Crawlera-Wait'] = self.x_crawlera_wait

    def init_request(self, request):
        if 'cookiejar' not in request.meta:
            request.meta['cookiejar'] = str(uuid.uuid1())
        if self.crawlera_session:
            request.headers['X-Crawlera-Session'] = 'create'
        self._adapt_request(request)
        return request

    def init_start_requests(self, wrapped):
        def _wrapper(spider):
            if not hasattr(spider, 'crawlera_sessions'):
                spider.crawlera_sessions = OrderedDict()
            for request in wrapped(spider):
                self.init_request(request)
                yield request
        _wrapper.__name__ = wrapped.__name__
        return _wrapper


class CrawleraSessionRedirectMiddleware(RedirectMiddleware):

    def process_response(self, request, response, spider):
        obj = super(CrawleraSessionRedirectMiddleware, self).process_response(request, response, spider)
        if isinstance(obj, Request):
            if 'X-Crawlera-Session' in response.headers:
                obj.headers['X-Crawlera-Session'] = response.headers['X-Crawlera-Session']
        return obj
