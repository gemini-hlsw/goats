# How-to Unit Tests

This directory contains unit tests, which should align with `goats` modules. Each module must have a corresponding test that passes before branch merging. The essential criterion for a unit test is to call all user-intended functions and classes, ensuring their expected behaviors.

While these tests only focus on externally visible functionalities, they help prevent unexpected effects from code changes. However, they don't necessarily validate the functions. Functional validation is crucial, either through unit tests or scripts.

As GitHub actions routinely run tests, it's vital to maintain them efficiently. Hence, lightweight datasets, either stored under `data` or simulated for each test, are used.

To execute the tests, run the command `pytest` at the repository level.
