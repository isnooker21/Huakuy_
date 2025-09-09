"""
🛡️ Support/Resistance Detection Engine
=====================================

HYBRID METHOD:
✅ Fractal Detection (High/Low patterns)
✅ Volume Profile Analysis
✅ Price Action Confirmation
✅ Dynamic Strength Scoring
✅ Flexible & Accurate Detection

AUTHOR: Advanced Trading System  
VERSION: 1.0.0
"""

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from simple_breakout_engine import SRLevel, CandleData, TimeFrame

logger = logging.getLogger(__name__)

@dataclass
class FractalPoint:
    """Fractal high/low point"""
    price: float
    time: datetime
    fractal_type: str  # "HIGH" or "LOW"
    strength: float
    volume: float

class SRDetectionEngine:
    """
    🛡️ Support/Resistance Detection Engine
    
    HYBRID APPROACH:
    ✅ Fractal Analysis - Find swing highs/lows
    ✅ Volume Profile - Confirm with volume
    ✅ Touch Count - Count price interactions
    ✅ Strength Scoring - Dynamic strength calculation
    ✅ Flexible Detection - Adapts to market conditions
    """
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.fractal_period = 5  # Look for fractals in 5-candle window
        self.min_touches = 2     # Minimum touches to confirm S/R
        self.max_age_hours = 24  # Maximum age for S/R levels
        self.price_tolerance = 10.0  # 10 points tolerance for XAUUSD
        
        # Historical data storage
        self.price_history = []  # List of CandleData
        self.fractal_points = []  # List of FractalPoint
        self.confirmed_levels = []  # List of SRLevel
        
        logger.info("🛡️ S/R Detection Engine initialized")
        logger.info(f"📊 Fractal Period: {self.fractal_period}, Min Touches: {self.min_touches}")
    
    def detect_sr_levels(self, candle_history: List[CandleData], 
                        current_price: float) -> List[SRLevel]:
        """
        🎯 Main S/R Detection Function
        
        PROCESS:
        1. Find Fractal Points (Swing Highs/Lows)
        2. Analyze Volume Profile
        3. Count Price Touches
        4. Calculate Strength Scores
        5. Filter & Rank Levels
        """
        try:
            if len(candle_history) < self.fractal_period * 2:
                logger.debug("🚫 Insufficient candle history for S/R detection")
                return []
            
            # 1. 🔍 Find Fractal Points
            fractal_points = self._find_fractal_points(candle_history)
            
            # 2. 📊 Analyze Volume Profile
            volume_zones = self._analyze_volume_profile(candle_history)
            
            # 3. 🛡️ Generate S/R Candidates
            sr_candidates = self._generate_sr_candidates(fractal_points, volume_zones)
            
            # 4. ✅ Validate & Score S/R Levels
            validated_levels = self._validate_sr_levels(sr_candidates, candle_history, current_price)
            
            # 5. 🏆 Filter & Rank by Strength
            final_levels = self._filter_and_rank_levels(validated_levels, current_price)
            
            logger.info(f"🛡️ S/R Detection: Found {len(final_levels)} levels")
            for level in final_levels[:5]:  # Log top 5
                logger.info(f"   {level.level_type}: {level.price:.2f} "
                           f"(Strength: {level.strength:.1f}, Touches: {level.touches})")
            
            return final_levels
            
        except Exception as e:
            logger.error(f"❌ S/R Detection error: {e}")
            return []
    
    def _find_fractal_points(self, candles: List[CandleData]) -> List[FractalPoint]:
        """
        🔍 Find Fractal High/Low Points
        
        FRACTAL HIGH: candle.high > all surrounding highs
        FRACTAL LOW: candle.low < all surrounding lows
        """
        fractals = []
        period = self.fractal_period
        
        for i in range(period, len(candles) - period):
            current = candles[i]
            
            # Check for Fractal High
            is_fractal_high = True
            for j in range(i - period, i + period + 1):
                if j != i and candles[j].high >= current.high:
                    is_fractal_high = False
                    break
            
            if is_fractal_high:
                strength = self._calculate_fractal_strength(candles, i, "HIGH")
                fractals.append(FractalPoint(
                    price=current.high,
                    time=current.time,
                    fractal_type="HIGH",
                    strength=strength,
                    volume=current.volume
                ))
            
            # Check for Fractal Low
            is_fractal_low = True
            for j in range(i - period, i + period + 1):
                if j != i and candles[j].low <= current.low:
                    is_fractal_low = False
                    break
            
            if is_fractal_low:
                strength = self._calculate_fractal_strength(candles, i, "LOW")
                fractals.append(FractalPoint(
                    price=current.low,
                    time=current.time,
                    fractal_type="LOW",
                    strength=strength,
                    volume=current.volume
                ))
        
        logger.debug(f"🔍 Found {len(fractals)} fractal points")
        return fractals
    
    def _calculate_fractal_strength(self, candles: List[CandleData], 
                                   index: int, fractal_type: str) -> float:
        """Calculate fractal strength based on price difference and volume"""
        current = candles[index]
        period = self.fractal_period
        
        if fractal_type == "HIGH":
            # Compare with surrounding highs
            surrounding_highs = [candles[i].high for i in range(index - period, index + period + 1) if i != index]
            if surrounding_highs:
                avg_surrounding = np.mean(surrounding_highs)
                price_diff = current.high - avg_surrounding
            else:
                price_diff = 0
        else:  # LOW
            # Compare with surrounding lows
            surrounding_lows = [candles[i].low for i in range(index - period, index + period + 1) if i != index]
            if surrounding_lows:
                avg_surrounding = np.mean(surrounding_lows)
                price_diff = avg_surrounding - current.low
            else:
                price_diff = 0
        
        # Volume factor
        recent_volumes = [candles[i].volume for i in range(max(0, index - 10), index + 1)]
        avg_volume = np.mean(recent_volumes) if recent_volumes else current.volume
        volume_factor = current.volume / avg_volume if avg_volume > 0 else 1.0
        
        # Calculate strength (0-100)
        strength = min(100.0, (price_diff * volume_factor) / 10.0 + 50.0)
        return max(0.0, strength)
    
    def _analyze_volume_profile(self, candles: List[CandleData]) -> Dict[float, float]:
        """
        📊 Analyze Volume Profile
        
        Find price levels with high volume concentration
        """
        if not candles:
            return {}
        
        # Create price bins
        min_price = min(c.low for c in candles)
        max_price = max(c.high for c in candles)
        price_range = max_price - min_price
        bin_size = price_range / 50  # 50 price bins
        
        volume_profile = {}
        
        for candle in candles:
            # Distribute volume across candle range
            candle_range = candle.high - candle.low
            if candle_range > 0:
                volume_per_point = candle.volume / candle_range
                
                # Add volume to each price level in candle range
                current_price = candle.low
                while current_price <= candle.high:
                    bin_price = round(current_price / bin_size) * bin_size
                    volume_profile[bin_price] = volume_profile.get(bin_price, 0) + volume_per_point
                    current_price += bin_size / 2
        
        return volume_profile
    
    def _generate_sr_candidates(self, fractals: List[FractalPoint], 
                               volume_zones: Dict[float, float]) -> List[SRLevel]:
        """Generate S/R level candidates from fractals and volume"""
        candidates = []
        
        # From Fractal Points
        for fractal in fractals:
            level_type = "RESISTANCE" if fractal.fractal_type == "HIGH" else "SUPPORT"
            
            candidates.append(SRLevel(
                price=fractal.price,
                strength=fractal.strength,
                level_type=level_type,
                touches=1,  # Will be recalculated
                last_touch=fractal.time
            ))
        
        # From Volume Profile (High Volume Areas)
        if volume_zones:
            avg_volume = np.mean(list(volume_zones.values()))
            high_volume_threshold = avg_volume * 1.5
            
            for price, volume in volume_zones.items():
                if volume > high_volume_threshold:
                    candidates.append(SRLevel(
                        price=price,
                        strength=min(100.0, (volume / avg_volume) * 20),
                        level_type="SUPPORT",  # Will be determined later
                        touches=1,
                        last_touch=datetime.now()
                    ))
        
        return candidates
    
    def _validate_sr_levels(self, candidates: List[SRLevel], 
                           candles: List[CandleData], current_price: float) -> List[SRLevel]:
        """
        ✅ Validate S/R Levels
        
        - Count actual price touches
        - Determine Support/Resistance type
        - Calculate final strength
        """
        validated = []
        
        for candidate in candidates:
            # Count touches
            touches = self._count_price_touches(candidate.price, candles)
            
            if touches < self.min_touches:
                continue  # Not enough touches
            
            # Determine level type based on current price
            if current_price > candidate.price:
                level_type = "SUPPORT"
            else:
                level_type = "RESISTANCE"
            
            # Calculate final strength
            final_strength = self._calculate_final_strength(
                candidate, touches, candles, current_price
            )
            
            validated.append(SRLevel(
                price=candidate.price,
                strength=final_strength,
                level_type=level_type,
                touches=touches,
                last_touch=candidate.last_touch
            ))
        
        return validated
    
    def _count_price_touches(self, target_price: float, candles: List[CandleData]) -> int:
        """Count how many times price touched this level"""
        touches = 0
        tolerance = self.price_tolerance
        
        for candle in candles:
            # Check if candle touched the level
            if (candle.low <= target_price + tolerance and 
                candle.high >= target_price - tolerance):
                touches += 1
        
        return touches
    
    def _calculate_final_strength(self, candidate: SRLevel, touches: int,
                                 candles: List[CandleData], current_price: float) -> float:
        """Calculate final strength score for S/R level"""
        base_strength = candidate.strength
        
        # Touch count factor (more touches = stronger)
        touch_factor = min(2.0, touches / 3.0)
        
        # Distance factor (closer levels are more relevant)
        distance = abs(current_price - candidate.price)
        max_relevant_distance = 500.0  # 500 points for XAUUSD
        distance_factor = max(0.1, 1.0 - (distance / max_relevant_distance))
        
        # Age factor (newer levels are more relevant)
        if candidate.last_touch:
            hours_ago = (datetime.now() - candidate.last_touch).total_seconds() / 3600
            age_factor = max(0.1, 1.0 - (hours_ago / self.max_age_hours))
        else:
            age_factor = 0.5
        
        # Combine factors
        final_strength = base_strength * touch_factor * distance_factor * age_factor
        return min(100.0, final_strength)
    
    def _filter_and_rank_levels(self, levels: List[SRLevel], 
                               current_price: float) -> List[SRLevel]:
        """Filter and rank S/R levels by strength"""
        # Filter by minimum strength
        min_strength = 30.0
        filtered = [level for level in levels if level.strength >= min_strength]
        
        # Remove duplicates (similar price levels)
        unique_levels = []
        for level in filtered:
            is_duplicate = False
            for existing in unique_levels:
                if abs(level.price - existing.price) < self.price_tolerance:
                    # Keep the stronger one
                    if level.strength > existing.strength:
                        unique_levels.remove(existing)
                        unique_levels.append(level)
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_levels.append(level)
        
        # Sort by strength (strongest first)
        ranked_levels = sorted(unique_levels, key=lambda x: x.strength, reverse=True)
        
        # Return top levels only
        return ranked_levels[:10]  # Top 10 levels

def create_sr_detection_engine(symbol: str) -> SRDetectionEngine:
    """Factory function to create S/R Detection Engine"""
    return SRDetectionEngine(symbol)
