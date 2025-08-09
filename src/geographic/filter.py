import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from geopy import distance
from geopy.geocoders import Nominatim
import time

from ..database.models import GeographicRegion

class GeographicFilter:
    """
    Geographic filtering system to conserve credits by focusing on 
    LA region + south to Mexico border
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.geocoder = Nominatim(user_agent="bidnet-hvac-scraper")
        
        # Target counties in order of priority
        self.target_counties = {
            'los angeles': GeographicRegion.LOS_ANGELES,
            'orange': GeographicRegion.ORANGE,
            'san diego': GeographicRegion.SAN_DIEGO,
            'riverside': GeographicRegion.RIVERSIDE,
            'san bernardino': GeographicRegion.SAN_BERNARDINO,
            'imperial': GeographicRegion.IMPERIAL,
            'ventura': GeographicRegion.VENTURA
        }
        
        # Central Los Angeles coordinates for distance calculations
        self.la_center = (34.0522, -118.2437)
        
        # Maximum distance from LA (in miles) - roughly 1.5 hours drive
        self.max_distance_miles = 150
        
        # Cache for geocoding results to avoid API limits
        self.location_cache = {}
        
    def is_in_target_region(self, location_text: str) -> Tuple[bool, GeographicRegion]:
        """
        Determine if a location is within our target region
        
        Args:
            location_text: Location string to analyze
            
        Returns:
            Tuple of (is_in_region: bool, region: GeographicRegion)
        """
        if not location_text:
            return False, GeographicRegion.OUT_OF_REGION
        
        location_lower = location_text.lower()
        
        # Quick county-based filtering (most efficient)
        region = self._check_county_keywords(location_lower)
        if region != GeographicRegion.OUT_OF_REGION:
            return True, region
        
        # City-based filtering for major cities
        region = self._check_city_keywords(location_lower)
        if region != GeographicRegion.OUT_OF_REGION:
            return True, region
        
        # Geocoding as last resort (API limited)
        try:
            region = self._check_geocoded_location(location_text)
            if region != GeographicRegion.OUT_OF_REGION:
                return True, region
        except Exception as e:
            self.logger.debug(f"Geocoding failed for '{location_text}': {e}")
        
        # If we get here, it's likely out of region
        self.logger.debug(f"Location '{location_text}' determined to be out of target region")
        return False, GeographicRegion.OUT_OF_REGION
    
    def _check_county_keywords(self, location_lower: str) -> GeographicRegion:
        """Check for county keywords in location text"""
        for county, region in self.target_counties.items():
            county_patterns = [
                f"{county} county",
                f"{county} co",
                f"county of {county}",
                f"{county}, ca",
                f"{county}, california"
            ]
            
            for pattern in county_patterns:
                if pattern in location_lower:
                    self.logger.debug(f"Matched county pattern: {pattern}")
                    return region
        
        return GeographicRegion.OUT_OF_REGION
    
    def _check_city_keywords(self, location_lower: str) -> GeographicRegion:
        """Check for major city keywords"""
        # Major cities by county
        city_mappings = {
            GeographicRegion.LOS_ANGELES: [
                'los angeles', 'santa monica', 'beverly hills', 'hollywood',
                'pasadena', 'glendale', 'burbank', 'torrance', 'inglewood',
                'el segundo', 'culver city', 'west hollywood', 'manhattan beach',
                'redondo beach', 'hermosa beach', 'long beach', 'compton',
                'downey', 'norwalk', 'whittier', 'pomona', 'covina',
                'west covina', 'alhambra', 'monterey park', 'arcadia'
            ],
            GeographicRegion.ORANGE: [
                'anaheim', 'santa ana', 'irvine', 'huntington beach', 'garden grove',
                'orange', 'fullerton', 'costa mesa', 'mission viejo', 'westminster',
                'newport beach', 'buena park', 'tustin', 'yorba linda',
                'san clemente', 'laguna beach', 'fountain valley', 'placentia'
            ],
            GeographicRegion.SAN_DIEGO: [
                'san diego', 'chula vista', 'oceanside', 'escondido', 'carlsbad',
                'el cajon', 'vista', 'san marcos', 'encinitas', 'national city',
                'la mesa', 'santee', 'poway', 'coronado', 'del mar'
            ],
            GeographicRegion.RIVERSIDE: [
                'riverside', 'moreno valley', 'corona', 'temecula', 'murrieta',
                'hemet', 'palm springs', 'cathedral city', 'desert hot springs',
                'indio', 'la quinta', 'palm desert', 'coachella', 'beaumont',
                'banning', 'perris', 'lake elsinore', 'menifee'
            ],
            GeographicRegion.SAN_BERNARDINO: [
                'san bernardino', 'fontana', 'rancho cucamonga', 'ontario',
                'victorville', 'rialto', 'chino', 'chino hills', 'upland',
                'redlands', 'hesperia', 'apple valley', 'colton', 'montclair',
                'barstow', 'twentynine palms', 'yucaipa', 'highland'
            ],
            GeographicRegion.VENTURA: [
                'ventura', 'oxnard', 'thousand oaks', 'simi valley', 'camarillo',
                'moorpark', 'fillmore', 'santa paula', 'ojai', 'port hueneme'
            ],
            GeographicRegion.IMPERIAL: [
                'el centro', 'calexico', 'imperial', 'brawley', 'calipatria',
                'westmorland', 'holtville'
            ]
        }
        
        for region, cities in city_mappings.items():
            for city in cities:
                if city in location_lower:
                    self.logger.debug(f"Matched city: {city} -> {region}")
                    return region
        
        return GeographicRegion.OUT_OF_REGION
    
    def _check_geocoded_location(self, location_text: str) -> GeographicRegion:
        """Use geocoding to check if location is within target region"""
        # Check cache first
        if location_text in self.location_cache:
            return self.location_cache[location_text]
        
        # Rate limiting for geocoding API
        time.sleep(0.1)
        
        try:
            # Geocode the location
            location = self.geocoder.geocode(f"{location_text}, CA, USA")
            
            if not location:
                self.logger.debug(f"Could not geocode: {location_text}")
                self.location_cache[location_text] = GeographicRegion.OUT_OF_REGION
                return GeographicRegion.OUT_OF_REGION
            
            # Calculate distance from LA center
            coords = (location.latitude, location.longitude)
            distance_miles = distance.distance(self.la_center, coords).miles
            
            self.logger.debug(f"'{location_text}' is {distance_miles:.1f} miles from LA")
            
            if distance_miles <= self.max_distance_miles:
                # Determine which region based on approximate location
                region = self._determine_region_by_coordinates(coords)
                self.location_cache[location_text] = region
                return region
            else:
                self.location_cache[location_text] = GeographicRegion.OUT_OF_REGION
                return GeographicRegion.OUT_OF_REGION
                
        except Exception as e:
            self.logger.debug(f"Geocoding error for '{location_text}': {e}")
            self.location_cache[location_text] = GeographicRegion.OUT_OF_REGION
            return GeographicRegion.OUT_OF_REGION
    
    def _determine_region_by_coordinates(self, coords: Tuple[float, float]) -> GeographicRegion:
        """Determine region based on coordinates"""
        lat, lng = coords
        
        # Rough geographic bounds for each county
        # These are approximate and meant for basic classification
        if lat >= 34.3 and lng >= -118.7 and lng <= -117.6:  # Ventura area
            return GeographicRegion.VENTURA
        elif lat >= 33.7 and lat <= 34.8 and lng >= -118.9 and lng <= -117.6:  # LA area
            return GeographicRegion.LOS_ANGELES
        elif lat >= 33.4 and lat <= 34.2 and lng >= -118.2 and lng <= -117.4:  # Orange area
            return GeographicRegion.ORANGE
        elif lat >= 32.5 and lat <= 33.8 and lng >= -117.6 and lng <= -116.1:  # San Diego area
            return GeographicRegion.SAN_DIEGO
        elif lat >= 33.4 and lat <= 34.3 and lng >= -117.6 and lng <= -116.2:  # Riverside area
            return GeographicRegion.RIVERSIDE
        elif lat >= 33.7 and lat <= 35.3 and lng >= -118.1 and lng <= -116.0:  # San Bernardino area
            return GeographicRegion.SAN_BERNARDINO
        elif lat >= 32.5 and lat <= 33.3 and lng >= -116.0 and lng <= -114.6:  # Imperial area
            return GeographicRegion.IMPERIAL
        else:
            return GeographicRegion.OUT_OF_REGION
    
    def filter_contracts_by_geography(self, contracts: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Filter contracts by geographic region
        
        Args:
            contracts: List of contract dictionaries
            
        Returns:
            Tuple of (in_region_contracts, out_of_region_contracts)
        """
        in_region = []
        out_of_region = []
        
        self.logger.info(f"Filtering {len(contracts)} contracts by geography...")
        
        for contract in contracts:
            location = contract.get('location', '')
            is_in_region, region = self.is_in_target_region(location)
            
            # Add region info to contract
            contract['geographic_region'] = region.value
            contract['in_target_region'] = is_in_region
            
            if is_in_region:
                in_region.append(contract)
                self.logger.debug(f"✅ Kept: {contract.get('title', 'No title')[:50]} ({region.value})")
            else:
                out_of_region.append(contract)
                self.logger.debug(f"❌ Filtered out: {contract.get('title', 'No title')[:50]} ({location})")
        
        self.logger.info(f"Geographic filtering: {len(in_region)} in region, {len(out_of_region)} out of region")
        
        return in_region, out_of_region
    
    def get_region_priority_score(self, region: GeographicRegion) -> int:
        """Get priority score for region (higher = more important)"""
        priority_map = {
            GeographicRegion.LOS_ANGELES: 10,
            GeographicRegion.ORANGE: 9,
            GeographicRegion.SAN_DIEGO: 8,
            GeographicRegion.RIVERSIDE: 7,
            GeographicRegion.SAN_BERNARDINO: 6,
            GeographicRegion.VENTURA: 5,
            GeographicRegion.IMPERIAL: 4,
            GeographicRegion.OUT_OF_REGION: 0
        }
        return priority_map.get(region, 0)