"""
PulseTraffic OS - Root Data Sources Export
Exposes fetch_soilgrids_properties directly for external test runners and integrations.
"""

from traffic.data_sources import fetch_soilgrids_properties, _SOILGRIDS_CACHE

__all__ = ["fetch_soilgrids_properties", "_SOILGRIDS_CACHE"]
