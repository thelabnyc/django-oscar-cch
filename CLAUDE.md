# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

django-oscar-cch is a Django package that integrates django-oscar e-commerce sites with the CCH Sales Tax Office SOAP API for sales tax calculation. The package calculates taxes for basket items and shipping charges by calling CCH's web service, then persists taxation details in the database.

Full documentation: https://django-oscar-cch.readthedocs.io

## Development Commands

**IMPORTANT: All commands must be run via Docker Compose using the `test` service.**

### Environment Setup
```bash
# Build the Docker environment
docker compose build

# Sync dependencies (uses uv)
docker compose run --rm test uv sync --all-extras

# Install pre-commit hooks (run locally, not in Docker)
make install_precommit
# OR
pre-commit install
```

### Testing
```bash
# Run all tests with tox (tests multiple Python/Django/Oscar combinations)
docker compose run --rm test uv run tox

# Run tests for specific environment
docker compose run --rm test bash -c 'TOX_SKIP_ENV="^(?!py312-)" uv run tox'

# Run tests directly using manage.py
docker compose run --rm test python manage.py test oscarcch --noinput

# Run single test file
docker compose run --rm test python manage.py test oscarcch.tests.test_cch

# Run tests with coverage
docker compose run --rm test bash -c 'coverage erase && coverage run --source oscarcch -p manage.py test oscarcch --noinput && coverage combine && coverage report -m'
```

### Type Checking
```bash
# Run mypy type checking
docker compose run --rm test uv run mypy oscarcch/ sandbox/
```

### Code Quality
```bash
# Format code with ruff
docker compose run --rm test ruff format .

# Run pre-commit hooks (run locally, not in Docker)
make test_precommit
# OR
pre-commit run --all-files
```

### Building
```bash
# Build package distribution
docker compose run --rm test uv build
```

## Architecture

### Core Components

**CCHTaxCalculator** (`oscarcch/calculator.py`):
- Main interface to CCH Sales Tax Office SOAP API
- Uses zeep library for SOAP communication
- `apply_taxes()` method calculates taxes for basket and shipping, applying results to price objects
- Supports circuit breaker pattern (pybreaker integration)
- Converts Oscar basket/address models to CCH Order format via `_build_order()`
- Handles retry logic and error message parsing

**Models** (`oscarcch/models.py`):
- `OrderTaxation`: Top-level tax data for an order (transaction ID, status, total tax)
- `LineItemTaxation`: Tax details for individual order lines
- `LineItemTaxationDetail`: Individual tax types applied to a line (uses PostgreSQL HStore)
- `ShippingTaxation`: Tax details for shipping charges
- `ShippingTaxationDetail`: Individual tax types applied to shipping
- All models have `save_details()` class methods to persist CCH SOAP responses

**Mixins** (`oscarcch/mixins.py`):
- `CCHOrderMixin`: Adds `is_tax_known` field to Order model
- `CCHOrderLineMixin`: Adds `basket_line` foreign key to OrderLine model
- `CCHOrderCreatorMixin`: Overrides `place_order()` to call CCH, calculate taxes, then persist order and taxation details atomically

**Prices** (`oscarcch/prices.py`):
- Monkey-patches Oscar's Price classes with `add_tax()`, `clear_taxes()`, and `taxation_details` list
- `ShippingCharge`: Container for multiple shipping charge components
- `ShippingChargeComponent`: Individual shipping charge with CCH line ID and SKU

**Settings** (`oscarcch/settings.py`):
- Defines all CCH configuration settings with Django setting overrides
- Required settings: `CCH_WSDL`, `CCH_ENTITY`, `CCH_DIVISION`
- Optional settings for timeouts, retries, product codes, timezone, etc.

### Integration Pattern

To integrate with django-oscar:

1. **Fork Oscar's Order models** (see `sandbox/order/models.py`):
   - Mix `CCHOrderMixin` into Order model
   - Mix `CCHOrderLineMixin` into Line model

2. **Fork Oscar's OrderCreator** (see `sandbox/order/utils.py`):
   - Mix `CCHOrderCreatorMixin` into OrderCreator class
   - This automatically calls CCH during order placement

3. **Call monkey_patch_prices()** early in Django startup (typically in AppConfig.ready())

4. **Configure required Django settings**:
   - `CCH_WSDL`: Full URL to CCH WSDL file
   - `CCH_ENTITY`: Entity code for CCH
   - `CCH_DIVISION`: Division code for CCH

### Tax Calculation Flow

1. User proceeds to checkout with basket and shipping address
2. `CCHOrderCreatorMixin.place_order()` is called
3. Creates `ShippingCharge` object if needed
4. Calls `CCHTaxCalculator().apply_taxes(shipping_address, basket, shipping_charge)`
5. Calculator builds CCH Order object from basket lines and shipping components
6. Makes SOAP call to CCH API with retry logic
7. Parses response and applies taxes to each Price object via `add_tax()`
8. Returns CCH response (or None on error)
9. Recalculates order total with taxes included
10. Saves order in database transaction
11. Calls `OrderTaxation.save_details()` to persist CCH response
12. Returns completed order

### Product Configuration

Products can override default CCH codes via Product attributes:
- `cch_product_sku`: Custom SKU (default: `CCH_PRODUCT_SKU` setting)
- `cch_product_group`: Product group code (default: `CCH_PRODUCT_GROUP` setting)
- `cch_product_item`: Product item code (default: `CCH_PRODUCT_ITEM` setting)

Basket lines can override quantity sent to CCH via `cch_quantity` attribute.

## Testing Environment

The `sandbox/` directory contains a minimal django-oscar project for testing:
- Uses local WSDL file at `sandbox/wsdl/cch.xml`
- Configured with test CCH entity/division
- PostgreSQL database required (uses HStoreField)
- Docker Compose available for running tests in container

## Type Checking Configuration

- Uses mypy with django-stubs plugin
- Strict mode enabled (see `tool.mypy` in pyproject.toml)
- Migrations and test files ignore errors
- Oscar module uses `follow_untyped_imports = true`
- Python 3.12 target

## Supported Versions

Tested with:
- Python: 3.12, 3.13
- Django: 4.2, 5.1, 5.2
- django-oscar: 3.2, 4.0

## Dependencies

Key dependencies:
- zeep: SOAP client library
- django-stubs-ext: Django typing support
- pybreaker: Circuit breaker pattern
