# P10F Failed Validation Attempt 01

## Status

`failed_structural_validation`

## Cause

The generated draft referenced source filenames but omitted all
available page and line locators. The source_traceability_markers
validation check therefore failed.

## Resolution

A deterministic derived draft will add the four locators verified
in the accepted P10C source audit. The original generated draft
and generation summary remain immutable.
