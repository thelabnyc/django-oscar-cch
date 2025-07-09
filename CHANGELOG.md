# Changes

## v7.5.0 (2025-07-09)

### Feat

- test against django 5.2

### Fix

- update docker image tag format
- **deps**: update dependency django-oscar to >=4.0,<4.1
- **deps**: update dependency django-oscar to >=3.2.6,<4.1

### Refactor

- migrate from poetry -> uv

## v7.4.0 (2025-04-03)

### Feat

- add support for Django 5.0

### Fix

- **deps**: update dependency django to ^4.2.20
- **deps**: update dependency django-stubs-ext to ^5.1.3
- **deps**: update dependency django to ^4.2.19

### Refactor

- add pyupgrade / django-upgrade precommit hooks

## v7.3.3 (2025-02-05)

### Fix

- storage format of empty taxation messages

## v7.3.2 (2025-02-04)

### Fix

- circular import issues

## v7.3.1 (2025-02-04)

### Fix

- add proxy and timeout settings

## v7.3.0 (2025-02-04)

### Feat

- add type annotations
- migrate SOAP client from instrumented-soap to zeep

### Fix

- **deps**: update dependency django to ^4.2.18
- **deps**: update dependency django to ^4.2.17

## v7.2.2 (2024-09-25)

### Fix

- **deps**: update dependency django-oscar to v3.2.5
- pin django-oscar version due to breaking changes in patch versions
- **deps**: update dependency django to ^4.2.16
- **deps**: update dependency instrumented-soap to ^2.1.2

## v7.2.1 (2024-08-31)

### Fix

- **deps**: update dependency django to ^4.2.15

## v7.2.1b0 (2024-08-08)

### Fix

- **deps**: update dependency django to ^4.2.14
- **deps**: update dependency django to ^4.2.13
- **deps**: update dependency django-oscar to v3.2.4
- **deps**: update dependency django to v4.2.13

## v7.2.0

- Add support for django-oscar 3.2.2
- Add support for django 4.2

## v7.1.0

- Oscar 3.1 Compatibility

## v7.0.0

- Oscar 3.0 Compatibility

## v6.0.0


## v5.0.0

- Add support for calculating taxes on shipping charges.

## v4.0.1

- Handle case when CCH returns an error code during order placement.

## v4.0.0

- Remove StatsD counters and timers.

## v3.1.0

- Add ability to pass in a ``pybreaker.CircuitBreaker`` instance into the ``CCHTaxCalculator`` constructor. This allows implementing the CircuitBreaker pattern, thus enabling better handling of CCH web service outages. See the `pybreaker <https://github.com/danielfm/pybreaker>`_ documentation for implementation details.

## v3.0.0

- Add support for django-oscar 2.x.
- Drop support for django-oscar 1.x.

## v2.2.9

- Internationalization

## v2.2.8

- Fix a few more Django 2.0 deprecation warnings that were missed in ``2.2.7``.

## v2.2.7

- Fix Django 2.0 Deprecation warnings.

## v2.2.6

- Add support for Oscar 1.5 and Django 1.11.

## v2.2.5

- Detect 9-digit ZIP codes in shipping a warehouse addresses and, instead of truncating the last 4 digits, send them in the `Plus4` field of the SOAP request.

## v2.2.4

- [Important] Fix bug causing order lines to get deleted is the corresponding basket or basket line is deleted.

## v2.2.3

- Handle bug occurring when a basket contained a zero-quantity line item.

## v2.2.2

- Upgrade dependencies.

## v2.2.1

- Simplified retry logic and fixed infinite loop issue.

## v2.2.0

- Improved documentation.
- Added ability to retry CCH transactions when requests raises a ConnectionError, ConnectTimeout, or ReadTimeout.
    - Added new setting, ``CCH_MAX_RETRIES``, to control how many retries to attempt after an initial failure. Defaults to 2.

## v2.1.0

- Remove caching functionality from CCHTaxCalculator.estimate_taxes since miss rate was almost 100%.
- Fix bug in tax calculation causing taxes to be calculated based on pre-discounted prices instead of post-discounted prices.
- Add optional basket line quantity override by checking for property `BasketLine.cch_quantity`. Falls back to standard quantity if property doesn't exist.


## v2.0.0

- Renamed package to `oscarcch` for consistency. Set `db_table` option on models to prevent requiring table rename.
- Move tests inside `oscarcch` package.


## v1.1.1

- Fix bug where calculator could throw exception even when `ignore_cch_error` flag was set.


## v1.1.0

- Add the ability to set CCH product SKU, item, and group per-product in addition to globally.


## v1.0.5

- Add `CCH_TIME_ZONE` setting.
- Send time zone aware ISO format date as CalculateRequest InvoiceDate node. Formerly just sent the date.


## v1.0.4

- Truncate ZIP coes so that CCH doesn't choke when the user supplies a full 9-digit ZIP code.


## v1.0.3

- Improve unit tests by mocking all requests and responses. This allows running tests without a connection to an actual CCH server instance.
- Fixed bug where floats from SOAP response weren't properly converted into quantized decimals when saving `OrderTaxation` and `LineTaxation` models.


## v1.0.2

- Made `instrumented-soap` dependency optional.
- Moved gitlab testing from the shell executor to the docker executor.
- Added better usage documentation.


## v1.0.1

- Fixed an exception when `raven` isn't installed.


## v1.0.0

- Initial release.
