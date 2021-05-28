# README

Class that provides decorators and functions for easy handling of crawlera sessions in a scrapy spider.

# Installation

pip install crawlera-session

# Usage

Ensure `COOKIES_ENABLED` is set to True (otherwise there is no point in using this class)
Subclass your spider from `CrawleraSessionMixinSpider`.

Provided decorator must be applied for every callback that yields requests that
must conserve session. For starting requests, use `init_start_request`. This decorator will
instruct requests provided by start requests, to initiate each one a new session.

The callback that yields requests that must follow the session initiated previously within same
requests chain must be decorated with `follow_session`.

Example:

```python
from crawlera_session import CrawleraSessionMixinSpider, RequestSession

crawlera_session = RequestSession()


class MySpider(CrawleraSessionMixinSpider, Spider):

    @crawlera_session.init_start_requests
    def start_requests(self):
        ...
        yield Request(...)


    @crawlera_session.follow_session
    def parse(self, response):
        ...
        yield Request(...)
```

Some times you need to initialize a session for a single request generated in a spider method. In that case,
you can use `init_request()` method:

```python
    def parse(self, response):
        ...
        yield Request(...)
        ...
        yield crawlera_session.init_request(Request(...))
```


If on the contrary, you want to send a normal (not session) request from a callback that was decorated with `follow_session`,
you can use the `no_crawlera_session` meta tag:

```python
    @crawlera_session.follow_session
    def parse(self, response):
        ...
        yield Request(...)
        ...
        yield Request(..., meta={'no_crawlera_session': True})
```

In short, the logic `init_request->follow_session` makes a chain of requests to use the same session. So requests issued by callbacks
decorated by `follow_session` reuse the session created by the request which initiated it, in the same request chain as defined
by the spider logic.

However, there are use cases where you want to reuse a session initiated in another chain, instead of initiating a new one.
For that purpose, you can defer the session assignation of the requests until a previously created session is available for reusage
(when the chain that created it is completed). There are two other decorators that implements this logic: `defer_assign_session` and
`unlock_session`. Their logic must be used in combination of spider attribute `MAX_PARALLEL_SESSIONS`.

`defer_assign_session` makes requests yielded by the decorated callback:
* either to initiate a new request if number of initiated sessions is below `MAX_PARALLEL_SESSIONS` or `MAX_PARALLEL_SESSIONS` is None.
* or wait for an available session for reusage in other case.

In order to indicate the end of a request chain for unlocking its session for reusage, the last callback of the chain must be
decorated with `unlock_session`.

Example:

```python
from crawlera_session import CrawleraSessionMixinSpider, RequestSession

crawlera_session = RequestSession()


class MySpider(CrawleraSessionMixinSpider, Spider):

    MAX_PARALLEL_SESSIONS = 4

    def start_requests(self):
        ...
        yield Request(...)

    @crawlera_session.defer_assign_session
    def parse(self, response):
        ...
        yield Request(..., callback=callback2)

    @crawlera_session.follow_session
    def callback2(self, response):
        yield Request(..., callback=callback3)

    ...

    @crawlera_session.unlock_session
    def callbackN(self, response):
        yield Item(...)

```

For better performance, normally it is better to set the number of concurrent requests to the same as `MAX_PARALLEL_SESSIONS`.
Notice that if you don't set `MAX_PARALLEL_SESSIONS`, the behavior of the callback decorated by `defer_assign_session` will
be that all requests yielded by it will initiate a new session. That is, as if you applied `init_request()` to every request
yielded by it.
