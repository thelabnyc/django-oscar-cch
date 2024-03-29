.. _changelog:

Changelog
=========

7.2.0
------------------
- Add support for django-oscar 3.2.2
- Add support for django 4.2

7.1.0
------------------
- Oscar 3.1 Compatibility

7.0.0
------------------
- Oscar 3.0 Compatibility

6.0.0
------------------

5.0.0
------------------
- Add support for calculating taxes on shipping charges.

4.0.1
------------------
- Handle case when CCH returns an error code during order placement.

4.0.0
------------------
- Remove StatsD counters and timers.

3.1.0
------------------
- Add ability to pass in a ``pybreaker.CircuitBreaker`` instance into the ``CCHTaxCalculator`` constructor. This allows implementing the CircuitBreaker pattern, thus enabling better handling of CCH web service outages. See the `pybreaker <https://github.com/danielfm/pybreaker>`_ documentation for implementation details.

3.0.0
------------------
- Add support for django-oscar 2.x.
- Drop support for django-oscar 1.x.

2.2.9
------------------
- Internationalization

2.2.8
------------------
- Fix a few more Django 2.0 deprecation warnings that were missed in ``2.2.7``.

2.2.7
------------------
- Fix Django 2.0 Deprecation warnings.

2.2.6
------------------
- Add support for Oscar 1.5 and Django 1.11.

2.2.5
------------------
- Detect 9-digit ZIP codes in shipping a warehouse addresses and, instead of truncating the last 4 digits, send them in the `Plus4` field of the SOAP request.

2.2.4
------------------
- [Important] Fix bug causing order lines to get deleted is the corresponding basket or basket line is deleted.

2.2.3
------------------
- Handle bug occurring when a basket contained a zero-quantity line item.

2.2.2
------------------
- Upgrade dependencies.

2.2.1
------------------
- Simplified retry logic and fixed infinite loop issue.

2.2.0
------------------
- Improved documentation.
- Added ability to retry CCH transactions when requests raises a ConnectionError, ConnectTimeout, or ReadTimeout.
    - Added new setting, ``CCH_MAX_RETRIES``, to control how many retries to attempt after an initial failure. Defaults to 2.

2.1.0
------------------
- Remove caching functionality from CCHTaxCalculator.estimate_taxes since miss rate was almost 100%.
- Fix bug in tax calculation causing taxes to be calculated based on pre-discounted prices instead of post-discounted prices.
- Add optional basket line quantity override by checking for property `BasketLine.cch_quantity`. Falls back to standard quantity if property doesn't exist.


2.0.0
------------------
- Renamed package to `oscarcch` for consistency. Set `db_table` option on models to prevent requiring table rename.
- Move tests inside `oscarcch` package.


1.1.1
------------------
- Fix bug where calculator could throw exception even when `ignore_cch_error` flag was set.


1.1.0
------------------
- Add the ability to set CCH product SKU, item, and group per-product in addition to globally.


1.0.5
------------------
- Add `CCH_TIME_ZONE` setting.
- Send time zone aware ISO format date as CalculateRequest InvoiceDate node. Formerly just sent the date.


1.0.4
------------------
- Truncate ZIP coes so that CCH doesn't choke when the user supplies a full 9-digit ZIP code.


1.0.3
------------------
- Improve unit tests by mocking all requests and responses. This allows running tests without a connection to an actual CCH server instance.
- Fixed bug where floats from SOAP response weren't properly converted into quantized decimals when saving `OrderTaxation` and `LineTaxation` models.


1.0.2
------------------
- Made `instrumented-soap` dependency optional.
- Moved gitlab testing from the shell executor to the docker executor.
- Added better usage documentation.


1.0.1
------------------
- Fixed an exception when `raven` isn't installed.


1.0.0
------------------
- Initial release.
