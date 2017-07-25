import os
import datetime
from typing import Union
from PIL.Image import Image as PILImage

from datapipelines import NotFoundError
from merakicommons.ghost import ghost_load_on
from merakicommons.cache import lazy, lazy_property
from merakicommons.container import searchable, SearchableList

from ..configuration import settings
from ..data import Region, Platform
from .common import DataObject, CassiopeiaObject, CassiopeiaGhost, provide_default_region, get_latest_version
from .staticdata import ProfileIcon
from ..dto.summoner import SummonerDto

try:
    import ujson as json
except ImportError:
    import json


_profile_icon_names = None


##############
# Data Types #
##############


class ProfileIconData(DataObject):
    _renamed = {"id": "profileIconId"}

    @property
    def id(self) -> int:
        return self._dto["profileIconId"]


class AccountData(DataObject):
    _renamed = {"id": "accountId"}

    @property
    def id(self) -> int:
        return self._dto["accountId"]


class SummonerData(DataObject):
    _dto_type = SummonerDto
    _renamed = {"profile_icon": "profileIconId", "level": "summonerLevel", "revision_date": "revisionDate", "account": "accountId"}

    @property
    def region(self) -> str:
        return self._dto["region"]

    @property
    def account(self) -> AccountData:
        return AccountData(id=self._dto["accountId"])

    @property
    def id(self) -> int:
        return self._dto["id"]

    @property
    def name(self) -> str:
        return self._dto["name"]

    @property
    def level(self) -> str:
        return self._dto["summonerLevel"]

    @property
    def profile_icon_id(self) -> int:
        """ID of the summoner icon associated with the summoner."""
        return self._dto["profileIconId"]

    @property
    def revision_date(self) -> datetime.date:
        """Date summoner was last modified specified as epoch milliseconds. The following events will update this timestamp: profile icon change, playing the tutorial or advanced tutorial, finishing a game, summoner name change."""
        return self._dto["revisionDate"]


##############
# Core Types #
##############


@searchable({int: ["id"]})
class Account(CassiopeiaObject):
    _data_types = {AccountData}

    @property
    def id(self) -> int:
        return self._data[AccountData].id


@searchable({str: ["name", "region", "platform"], int: ["id", "account"], Region: ["region"], Platform: ["platform"]})
class Summoner(CassiopeiaGhost):
    _data_types = {SummonerData}

    @provide_default_region
    def __init__(self, *, id: int = None, account: Union[Account, int] = None, name: str = None, region: Union[Region, str]):
        kwargs = {"region": region}
        if id:
            kwargs["id"] = id
        if name:
            kwargs["name"] = name
        if account and isinstance(account, Account):
            self.__class__.account.fget._lazy_set(self, account)
        elif account:
            kwargs["account"] = account
        super().__init__(**kwargs)

    def __get_query__(self):
        query = {"region": self.region}
        try:
            query["id"] = self._data[SummonerData].id
        except KeyError:
            try:
                query["account.id"] = self._data[SummonerData].account.id
            except KeyError:
                query["name"] = self._data[SummonerData].name
        return query

    @property
    def exists(self):
        try:
            if not self._Ghost__all_loaded:
                self.__load__()
            self.revision_date  # Make sure we can access this attribute
            return True
        except (AttributeError, NotFoundError):
            return False

    @lazy_property
    def region(self) -> Region:
        """The region for this summoner."""
        return Region(self._data[SummonerData].region)

    @lazy_property
    def platform(self) -> Platform:
        """The platform for this summoner."""
        return self.region.platform

    @CassiopeiaGhost.property(SummonerData)
    @ghost_load_on(KeyError)
    @lazy
    def account(self) -> Account:
        return Account.from_data(self._data[SummonerData].account)

    @CassiopeiaGhost.property(SummonerData)
    @ghost_load_on(KeyError)
    def id(self) -> int:
        return self._data[SummonerData].id

    @CassiopeiaGhost.property(SummonerData)
    @ghost_load_on(KeyError)
    def name(self) -> str:
        return self._data[SummonerData].name

    @CassiopeiaGhost.property(SummonerData)
    @ghost_load_on(KeyError)
    def level(self) -> str:
        return self._data[SummonerData].level

    @CassiopeiaGhost.property(SummonerData)
    @ghost_load_on(KeyError)
    def profile_icon(self) -> ProfileIcon:
        return ProfileIcon(id=self._data[SummonerData].profile_icon_id)

    @CassiopeiaGhost.property(SummonerData)
    @ghost_load_on(KeyError)
    @lazy
    def revision_date(self) -> datetime.date:
        return datetime.datetime.fromtimestamp(self._data[SummonerData].revision_date / 1000).date()

    @property
    def match_history_uri(self) -> str:
        return "/v1/stats/player_history/{platform}/{id}".format(platform=self.platform.value, id=self.account.id)

    # Special core methods

    @property
    def champion_masteries(self):
        from .championmastery import ChampionMasteries
        return ChampionMasteries(summoner=self, region=self.region)

    @property
    def mastery_pages(self):
        from .masterypage import MasteryPages
        return MasteryPages(summoner=self, region=self.region)

    @property
    def rune_pages(self):
        from .runepage import RunePages
        return RunePages(summoner=self, region=self.region)

    @property
    def matches(self):
        from .match import MatchHistory
        return MatchHistory(summoner=self, region=self.region)

    def current_match(self):
        from .spectator import CurrentMatch
        return CurrentMatch(summoner=self, region=self.region)

    #def league(self):
    #    raise NotImplemented
    #def league_entry(self):
    #    raise NotImplemented
