import asyncio
import json
import logging
import re
import voluptuous as vol
import aiohttp
import random
from datetime import timedelta

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.discovery import async_load_platform

REQUIREMENTS = [ ]

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by antsz.hu"
CONF_NAME = 'name'

DEFAULT_NAME = 'Pollen HU'
DEFAULT_ICON = 'mdi:blur'

SCAN_INTERVAL = timedelta(hours=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    name = config.get(CONF_NAME)

    async_add_devices(
        [PollenHUSensor(hass, name )],update_before_add=True)

async def async_get_pdata(self):
    pjson = {}

    url = 'https://efop180.antsz.hu/polleninformaciok/'
    async with self._session.get(url) as response:
        rsp1 = await response.text()

    rsp = rsp1.replace("\n","").replace("\r","")

    p0 = re.findall(r"contentpagetitle\">.*</a></div><div class=\"ertek\">\d+",rsp)
    if len(p0) > 0:
        p1 = p0[0].replace(" </a>","</a>") \
             .replace("contentpagetitle\">",">\"name\":\"") \
             .replace("ertek\">",">\"value\":\"")
        clean = re.compile('<.*?>')
        p2 = re.sub(clean, ' ', p1)
        p3 = re.sub(r"([0-9])",r"\1 ",p2) \
             .replace("contentpagetitle\">", '') \
             .replace("  ","") \
             .replace(" \"","\",\"") \
             .replace("\",\"name","\"},{\"name") \
             .replace(">", "{\"pollens\":[{") + "\"}]}"
        pjson = json.loads(p3)
    return pjson

class PollenHUSensor(Entity):

    def __init__(self, hass, name):
        """Initialize the sensor."""
        self._hass = hass
        self._name = name
        self._state = None
        self._pdata = []
        self._icon = DEFAULT_ICON
        self._session = async_get_clientsession(hass)

    @property
    def extra_state_attributes(self):
        attr = {}
        dominant_value = 0

        if 'pollens' in self._pdata:
            attr["pollens"] = self._pdata.get('pollens')
            num_values = [0, 0, 0, 0, 0]

            for item in self._pdata['pollens']:
                value = int(item.get('value'))
                if value>1:
                    num_values[value]+=1
                if value>dominant_value:
                    dominant_value=value

            attr["dominant_pollen_value"] = dominant_value
            attr["dominant_pollen"] = ""

            if dominant_value>0:
                attr["dominant_pollen"] = self.get_dominant_text(dominant_value)
                if dominant_value>2:
                    ext = self.get_dominant_text(dominant_value-1).lower()
                    if ext>'':
                        attr["dominant_pollen"] += ' ' + random.choice(['illetve','továbbá','azon kívül','ezen felül','és azt mondják,'])+' '
                        attr["dominant_pollen"] += ext
                if dominant_value==4 and num_values[2]>0 and num_values[2]<5:
                    ext = self.get_dominant_text(dominant_value-2).lower()
                    if ext>'':
                        attr["dominant_pollen"] += ' ' + random.choice(['illetve','továbbá','azon kívül','ezen felül','és azt mondják,'])+' '
                        attr["dominant_pollen"] += ext
                attr["dominant_pollen"] += "."

        attr["provider"] = CONF_ATTRIBUTION
        return attr

    def get_dominant_text(self, level):
        ret = ""
        koncentraciok=["", "Alacsony", "Közepes", "Magas", "Nagyon magas"]
        dominansok = []
        for item in self._pdata['pollens']:
            if int(item.get('value'))==level:
                dominansok.append(self.nevelo(item.get('name')) + " " + item.get('name').lower())
        for i in range(len(dominansok)):
            if i>0:
                if i==len(dominansok)-1:
                    ret += " és "
                else:
                    ret += ", "
            ret += dominansok[i]
        if ret>'':
            ret=koncentraciok[level] + " koncentrációban " + ret

        return ret


    @asyncio.coroutine
    async def async_update(self):
        dominant_value = 0

        pdata = await async_get_pdata(self)

        self._pdata = pdata
        if 'pollens' in self._pdata:
            for item in self._pdata['pollens']:
                val = item.get('value')
                if int(val) > dominant_value:
                    dominant_value = int(val)

        self._state = dominant_value
        return self._state

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        return DEFAULT_ICON

    def nevelo(self, szoveg):
        if szoveg[0].upper() in ['A', 'Á', 'E', 'É', 'I', 'Í', 'O', 'Ó', 'Ö', 'Ő', 'U', 'Ú', 'Ü', 'Ű']:
            return 'az'
        return 'a'
