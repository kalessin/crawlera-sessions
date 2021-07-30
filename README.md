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
        # this request will not initiate session
        yield Request(...)
        ...
        # this request will initiate session
        yield crawlera_session.init_request(Request(...))
```

Alternatively, and probably more elegant with better code separation, you could do:


```python
    def parse(self, response):
        ...
        # this request will not initiate session
        yield Request(...)

        # this request will initiate session
        yield from self.generate_init_requests(response)

    @crawlera_session.init_requests
    def generate_init_requests(self, response):
        ...
        yield Request(...)
```

The decorator `init_requests` (don't confuse with `init_request()` method just described) is similar to `init_start_request`
but decorates a callback instead of `start_requests()`.

If on the contrary, you want to send a normal (not session) request from a callback that was decorated with `follow_session`,
you can use the `no_crawlera_session` meta tag:

```python
    @crawlera_session.follow_session
    def parse(self, response):
        ...
        # this request will follow same session coming from response
        yield Request(...)
        ...
        # this request will not follow session
        yield Request(..., meta={'no_crawlera_session': True})
```

or, alternatively:

```python

    def parse(self, response):
        # this request will follow same session coming from response
        yield from generate_session_reqs(response)
        ...
        # this request will not follow session
        yield Request(...)

    @crawlera_session.follow_session
    def generate_session_reqs(self, response)
        ...
        yield Request(...)

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
be that all requests yielded by it will initiate a new session. So the lock/unlock logic doesn't have much sense.
In this case, you can just use `init_requests` decorator:


```python
from crawlera_session import CrawleraSessionMixinSpider, RequestSession

crawlera_session = RequestSession()


class MySpider(CrawleraSessionMixinSpider, Spider):

    MAX_PARALLEL_SESSIONS = 4

    def start_requests(self):
        ...
        yield Request(...)

    @crawlera_session.init_requests
    def parse(self, response):
        ...
        yield Request(..., callback=callback2)

    @crawlera_session.follow_session
    def callback2(self, response):
        yield Request(..., callback=callback3)

    ...

    @crawlera_session.discard_session
    def callbackN(self, response):
        yield Item(...)

```


Notice that in the last callback we replaced the decorator `unlock_session` by `discard_session`. This decorator is optional, but in
case your spider generates large amounts of requests, the memory usage can increase significantly if you don't drop unused sessions.
Regardless you need to use it or not for saving memory, it is still a good practice when you can apply it (in situations where there
are multiple final chain requests, it is not possible to drop a session when reaching any one of them).

By default, retrying a request uses the same session. However, frequently you need to reinitialize a session instead. The `RequestSession()`
object provides a decorator for indicating special retry treatment on specific requests. For example, if the requests yielded by `callback3()`
in the example above need to reinitialize session starting from the first request in the chain, you would write something like this:

```python

class MySpider(CrawleraSessionMixinSpider, Spider):

    (...)

    @crawlera_session.init_requests
    def parse(self, response):
        ...
        yield Request(..., callback=callback2)


    (...)

    @crawlera_session.new_session_on_retry
    @crawlera_session.follow_session
    def callback3(self, response):
        yield Request(..., callback=self.callback4)

    (...)

    def callback4_errback(self, failure) -> Request:
        return Request(..., callback=callback2)

```

Notice the introduction of a new decorator, `new_session_on_retry`, and the definition (in this case) of `callback4_errback()` method:

- Every response yielded by a callback decorated by  `new_session_on_retry`, will be assigned an errback with the same name as its
  callback, but with the `_errback` suffix appended.
- If this method is not implemented in the spider, an assertion error will be raised.
- Request returned by `callback_errback()` will be instructed internaly to initialize a new session, and the same errback will be
  assigned to it for further retries. So you don't need explicit action for it.

By default, the number of session retries for a given request will be 3. This default value can be overriden in the `RequestSession()`
object initialization, i.e.:

```python
crawlera_session = RequestSession(new_session_retries=5)
```

Finally, if you want to adjust priority on each successive request of a chain of requests, the `RequestSession()` instantiator admits
the parameter `priority_adjust`. For example, if you want to ensure that requests more advanced in the chain are sent before new
initial chain requests when you have multiple of them, you would rather use:

```python
crawlera_session = RequestSession(priority_adjust=1)
```
