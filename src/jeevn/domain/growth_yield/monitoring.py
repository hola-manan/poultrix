"""
Growth monitoring from NDVI time-series.
"""

from typing import Dict, Any


class GrowthMonitoring:
    """Monitor crop growth progress over time"""

    @staticmethod
    def analyze_growth_trajectory(ndvi_timeseries: list) -> Dict[str, Any]:
        if not ndvi_timeseries or len(ndvi_timeseries) < 2:
            return {
                "status": "insufficient_data",
                "message": "Need at least 2 data points for trend analysis"
            }

        ndvi_values = [x.get("ndvi", 0) for x in ndvi_timeseries]

        x_vals = list(range(len(ndvi_values)))
        mean_x = sum(x_vals) / len(x_vals)
        mean_y = sum(ndvi_values) / len(ndvi_values)

        numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_vals, ndvi_values))
        denominator = sum((x - mean_x) ** 2 for x in x_vals)

        if denominator == 0:
            trend_slope = 0
        else:
            trend_slope = numerator / denominator

        if trend_slope > 0.02:
            trend = "Strong positive growth"
        elif trend_slope > 0.005:
            trend = "Moderate growth"
        elif trend_slope > -0.005:
            trend = "Stagnant/Stable"
        elif trend_slope > -0.02:
            trend = "Moderate decline"
        else:
            trend = "Severe decline"

        return {
            "status": "analyzed",
            "trend": trend,
            "trend_slope": round(trend_slope, 4),
            "current_ndvi": round(ndvi_values[-1], 2),
            "ndvi_range": f"{min(ndvi_values):.2f} to {max(ndvi_values):.2f}",
            "mean_ndvi": round(mean_y, 2),
            "data_points": len(ndvi_values),
            "recommendation": GrowthMonitoring._get_growth_recommendation(trend, ndvi_values[-1])
        }

    @staticmethod
    def _get_growth_recommendation(trend: str, current_ndvi: float) -> str:
        if "decline" in trend:
            if current_ndvi < 0.40:
                return "Critical: Immediate intervention needed. Investigate stress factors (water, nutrients, pests)."
            else:
                return "Monitor closely. Increase observation frequency. Assess for stress factors."
        elif "stagnant" in trend:
            return "Monitor for any stress development. Maintain current practices."
        else:
            return "Good progress. Continue current management practices."
