#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os.path

from datetime import date

try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus

from .ages import AgeRestrictions
from .singleton import Singleton
from .network import *
from .itemlisting import *
from .users import *
from .common import findKey


class PrimeVideo(Singleton):
    """ Wrangler of all things Amazon.(com|co.uk|de|jp) """

    def __init__(self, globalsInstance, settingsInstance):
        self._g = globalsInstance
        self._s = settingsInstance
        self._initialiseDB()
        self._createDB(self._art_tbl)
        self.days_since_epoch = lambda: int(time.time() / 86400)
        self.prime = ''
        self.filter = {}
        self.lang = loadUser('lang')
        self.def_dtid = 'A43PXU4ZN2AL1'
        self.defparam = 'deviceTypeID={}' \
                        '&firmware=fmw:22-app:3.0.351.3955' \
                        '&softwareVersion=351' \
                        '&priorityLevel=2' \
                        '&format=json' \
                        '&featureScheme=mobile-android-features-v11' \
                        '&deviceID={}' \
                        '&version=1' \
                        '&screenWidth=sw800dp' \
                        '&osLocale={}&uxLocale={}' \
                        '&supportsPKMZ=false' \
                        '&isLiveEventsV2OverrideEnabled=true' \
                        '&swiftPriorityLevel=critical'.format(self.def_dtid, g.deviceID, self.lang, self.lang)

    def BrowseRoot(self):
        cm_wl = [(getString(30185) % 'Watchlist', 'RunPlugin(%s?mode=getListMenu&url=%s&export=1)' % (self._g.pluginid, self._g.watchlist))]
        cm_lb = [(getString(30185) % getString(30100), 'RunPlugin(%s?mode=getListMenu&url=%s&export=1)' % (self._g.pluginid, self._g.library))]
        if self._s.multiuser:
            addDir(getString(30134).format(loadUser('name')), 'switchUser', '', cm=self._g.CONTEXTMENU_MULTIUSER)
        if self._s.profiles:
            act, profiles = self.getProfiles()
            if act is not False:
                addDir(profiles[act][0], 'switchProfile', '', thumb=profiles[act][2])
        addDir('Watchlist', 'getPage', 'watchlist', cm=cm_wl)
        self.getPage(root=True)
        addDir(getString(30100), 'getPage', 'library', cm=cm_lb)
        addDir('Genres', 'getPage', 'find')
        addDir(getString(30108), 'Search', '')
        xbmcplugin.endOfDirectory(self._g.pluginhandle, updateListing=False, cacheToDisc=False)

    def getFilter(self, resp, root):
        filters = findKey('filters', resp)
        if len(filters) > 0 and 'refineCollection' in filters[0]:
            filters = filters[0]['refineCollection']

        for item in filters:
            if 'text' in item and item['text'] is not None:
                d = findKey('parameters', item)
                d['swiftId'] = item['id']
                self.filter[item['text']] = d

    def addCtxMenu(self, il, wl):
        cm = []
        ct = il['contentType']
        if ct in ['movie', 'episode', 'season', 'live']:
            wlmode = 1 if wl else 0
            cm.append((getString(wlmode + 30180) % getString(self._g.langID[ct]), 'RunPlugin(%s?mode=editWatchList&url=%s&opt=%s)'
                       % (self._g.pluginid, il['asins'], wlmode)))
        if ct in 'season':
            u = urlencode({'mode': 'getPage', 'url': 'details', 'page': '-1', 'opt': 'itemId=' + il['asins']})
            cm.append((getString(30182), 'Container.Update(%s?%s)' % (self._g.pluginid, u)))
        return cm

    def getPage(self, page='home', params='pageType=home&pageId=home', pagenr=1, root=False):
        url_path = ['', '/cdp/mobile/getDataByTransform/v1/', '/cdp/switchblade/android/getDataByJvmTransform/v1/']
        url_dict = {'home': {'p': 2, 'js': 'dv-android/landing/initial/v1.kt', 'q': ''},
                    'landing': {'p': 2, 'js': 'dv-android/landing/initial/v1.kt', 'q': '&removeFilters=false'},
                    'browse': {'p': 1, 'js': 'dv-android/browse/v2/browseInitial.js', 'q': ''},
                    'detail': {'p': 1, 'js': 'dv-android/detail/v2/user/v2.5.js', 'q': '&capabilities='},
                    'details': {'p': 1, 'js': 'android/atf/v3.jstl', 'q': '&capabilities='},
                    'watchlist': {'p': 1, 'js': 'dv-android/watchlist/watchlistInitial/v3.js', 'q': ''},
                    'library': {'p': 1, 'js': 'dv-android/library/libraryInitial/v2.js', 'q': ''},
                    'find': {'p': 1, 'js': 'dv-android/find/v1.js', 'q': '&pageId=findv2&pageType=home'},
                    'search': {'p': 1, 'js': 'dv-android/search/searchInitial/v3.js', 'q': ''},
                    'profiles': {'p': 2, 'js': 'dv-android/profiles/listPrimeVideoProfiles/v1.kt', 'q': ''}
                    }

        url = ''
        if page == 'cache':
            resp = self.loadCache(params)
        else:
            pg = url_dict.get(page, url_dict['home'])
            url = self._g.ATVUrl + url_path[pg['p']] +pg['js']
            params += pg['q']
            query_dict = parse_qs(params)
            url = url.replace('Initial', 'Next') if 'Initial' in url and int(query_dict.get('startIndex', ['0'])[0]) > 0 else url
            url = url.replace('initial', 'next') if 'initial' in url and 'startIndex' in query_dict else url
            resp = getURL('%s?%s&%s' % (url, self.defparam, params), useCookie=MechanizeLogin(True), headers=self._g.headers_android)
        LogJSON(resp)

        if resp:
            resp = resp.get('resource', resp)
            self.getFilter(resp, root)
            if root:
                self._createDB(self._cache_tbl)
                for item in resp['navigations']:
                    q = self.filterDict(findKey('parameters', item))
                    addDir(item['text'].title(), 'getPage', 'landing', opt=urlencode(q))
                return

            if page == 'profiles':
                return resp

            if page in ['watchlist', 'library'] and 'Initial' in url and 'serviceToken' not in query_dict:
                for k, v in self.filter.items():
                    addDir(k, 'getPage', page, opt=urlencode(v))
                xbmcplugin.endOfDirectory(g.pluginhandle)
                return

            if page == 'details':
                if pagenr == -2:
                    return resp
                if pagenr == -1 and 'seasons' in resp:
                    for item in resp['seasons']:
                        item.update({'contentType': 'seasonslist'})
                        il = self.getInfos(item, resp)
                        addDir(self.formatTitle(il), 'getPage', 'details', il, 'itemId=' + il['asins'])
                elif 'episodes' in resp:
                    for item in resp['episodes']:
                        il = self.getInfos(item, resp)
                        cm = self.addCtxMenu(il, page in 'watchlist')
                        addVideo(self.formatTitle(il), il['asins'], il, cm=cm)
                else:
                    il = self.getInfos(resp)
                    cm = self.addCtxMenu(il, page in 'watchlist')
                    addVideo(self.formatTitle(il), il['asins'], il, cm=cm)
                setContentAndView(il['contentType'])
                xbmc.executebuiltin('RunPlugin(%s?mode=processMissing)' % self._g.pluginid)
                return

            if page == 'landing':
                pgmodel = resp.get('paginationModel')
                if pgmodel:
                    q = findKey('parameters', pgmodel)
                    q['swiftId'] = pgmodel['id']
                    q['pageSize'] = 20
                    q['startIndex'] = 0
                    self.getPage(q['pageType'], urlencode(q))
                    return
            if page == 'find' and 'collections' in resp:
                for col in resp['collections']:
                    pt = findKey('pageType', col)
                    if pt == 'genre':
                        resp = col

            ct = 'files'
            col = findKey('collections', resp)
            if col:
                pgmodel = resp.get('paginationModel')
                pgtype = 'home'
                for item in col:
                    if item.get('headerText') is None:
                        continue
                    title = self.cleanTitle(item['headerText'])
                    prdata = item.get('presentationData', {})
                    facetxt = prdata.get('facetText')
                    col_act = item.get('collectionAction')
                    col_lst = item.get('collectionItemList')
                    col_typ = item.get('collectionType')
                    if facetxt is not None:
                        isprime = prdata.get('offerClassification', '') == 'PRIME'
                        isincl = item.get('containerMetadata', {}).get('entitlementCues', {}).get('entitledCarousel', 'Entitled') == 'Entitled'
                        if self._s.payCont:
                            if isprime:
                                facetxt = '[COLOR {}]{}[/COLOR]'.format(self._g.PrimeCol, facetxt)
                            if isincl is False:
                                facetxt = '[COLOR {}]{}[/COLOR]'.format(self._g.PayCol, facetxt)
                        title = '{} - {}'.format(facetxt, title)
                    # faceimg = item.get('presentationData', {}).get('facetImages', {}).get('UNFOCUSED', {}).get('url')
                    if col_act:
                        q = self.filterDict(findKey('parameters', col_act))
                        addDir(title, 'getPage', col_act['type'], opt=urlencode(q))
                    elif col_lst and 'heroCarousel' not in col_typ:
                        self.writeCache(item)
                        addDir(title, 'getPage', 'cache', opt=quote_plus(item['collectionId']))
                self._cacheDb.commit()
            else:
                titles = resp['titles'][0] if 'titles' in resp and len(resp.get('titles', {})) > 0 else resp
                pgmodel = titles.get('paginationModel')
                pgtype = page
                col = titles.get('collectionItemList', [])

                for item in col:
                    model = item['model']
                    if item['type'] in ['textLink', 'imageTextLink', 'imageLink']:
                        la = model['linkAction']
                        q = findKey('parameters', la)
                        q = self.filterDict(q) if q else {}
                        text = model.get('text', model.get('accessibilityDescription'))
                        thumb = model.get('imageUrl', None)
                        addDir(text, 'getPage', la['type'], opt=urlencode(q), thumb=thumb)
                    else:
                        il = self.getInfos(model)
                        cm = self.addCtxMenu(il, page in 'watchlist')
                        ct = il['contentType']
                        if ct in ['movie', 'episode', 'live', 'videos']:
                            addVideo(self.formatTitle(il), il['asins'], il, cm=cm)
                        else:
                            pgnr = -1 if self._s.dispShowOnly and ct in 'season' else 1
                            addDir(self.formatTitle(il), 'getPage', 'details', infoLabels=il, opt='itemId=' + il['asins'], cm=cm, page=pgnr)

            if pgmodel and page != 'cache':
                nextp = findKey('parameters', pgmodel)
                if 'startIndex' not in nextp:
                    nextp['startIndex'] = pgmodel['startIndex']
                    nextp['pageSize'] = 40
                    nextp['swiftId'] = pgmodel['id']
                    pagenr += 1
                else:
                    nextp['pageSize'] = len(col)
                    pagenr = int(nextp['startIndex'] / len(col) + 1)
                addDir(' --= %s =--' % (getString(30111) % pagenr), 'getPage', pgtype, opt=urlencode(nextp), page=pagenr, thumb=self._s.NextIcon)

            setContentAndView(ct)
            xbmc.executebuiltin('RunPlugin(%s?mode=processMissing)' % self._g.pluginid)
        return

    def formatTitle(self, il):
        name = il['title']
        if il['contentType'] in 'episode':
            if il['episode'] > 0:
                name = '{}. {}'.format(il['episode'], name)
        if not il['isPrime'] and self._s.payCont:
            name = '[COLOR %s]%s[/COLOR]' % (self._g.PayCol, name)
        return name

    def writeCache(self, content):
        c = self._cacheDb.cursor()
        c.execute('insert or ignore into {} values (?,?)'.format(self._cache_tbl), [quote_plus(content['collectionId']), json.dumps(content)])
        c.close()

    def loadCache(self, col_id):
        c = self._cacheDb.cursor()
        result = c.execute('select content from {} where id = (?)'.format(self._cache_tbl), (col_id,)).fetchone()
        if result and len(result) > 0:
            return json.loads(result[0])
        return {}

    def Search(self, searchString=None):
        if searchString is None:
            searchString = self._g.dialog.input(getString(24121))
        if searchString:
            self.getPage('search', 'phrase={}'.format(quote_plus(searchString)))

    def editWatchList(self, asin, remove):
        act = 'RemoveTitleFromList' if remove > 0 else 'AddTitleToList'
        params = 'titleId={}'.format(asin)
        url = '{}/cdp/discovery/{}'.format(self._g.ATVUrl, act)
        resp = getURL('%s?%s&%s' % (url, self.defparam, params), useCookie=MechanizeLogin(True))['message']
        msg = resp['body']['message']
        Log(msg)
        if resp.get('statusCode', '') == 'SUCCESS':
            if remove:
                cPath = xbmc.getInfoLabel('Container.FolderPath')
                xbmc.executebuiltin('Container.Update("{}", replace)'.format(cPath))
        else:
            g.dialog.notification(g.__plugin__, msg, xbmcgui.NOTIFICATION_ERROR)

    def _createDB(self, table):
        c = self._cacheDb.cursor()
        if table == self._cache_tbl:
            c.execute('drop table if exists %s' % self._cache_tbl)
            c.execute('''CREATE TABLE %s(
                        id TEXT,
                        content TEXT,
                        PRIMARY KEY(id)
                        );''' % self._cache_tbl)
            self._cacheDb.commit()
        elif table == self._art_tbl:
            c = self._db.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS %s(
                        asin TEXT UNIQUE,
                        season INTEGER,
                        info TEXT,
                        date INTEGER,
                        PRIMARY KEY(asin, season)
                        );''' % self._art_tbl)
            c.execute('''CREATE TABLE IF NOT EXISTS miss(
                        asins TEXT UNIQUE,
                        title TEXT,
                        year TEXT,
                        content TEXT,
                        info TEXT,
                        PRIMARY KEY(asins, title)
                        );''')
            self._db.commit()
        c.close()

    def _initialiseDB(self):
        from sqlite3 import dbapi2 as sqlite
        self._cache_tbl = 'cache'
        self._art_tbl = 'art'
        self._dbFile = os.path.join(self._g.DATA_PATH, 'art-%s.db' % self._g.MarketID)
        self._db = sqlite.connect(self._dbFile)
        self._cacheFile = os.path.join(self._g.DATA_PATH, 'cache-%s.db' % self._g.MarketID)
        self._cacheDb = sqlite.connect(self._cacheFile)
        self._createDB(self._art_tbl)

    @staticmethod
    def cleanTitle(title):
        if title.isupper():
            title = title.title().replace('[Ov]', '[OV]').replace('Bc', 'BC')
        title = title.replace('\u2013', '-').replace('\u00A0', ' ').replace('[dt./OV]', '').replace('_DUPLICATE_', '')
        return title.strip()

    def getArtandInfo(self, infoLabels, contentType, item):
        infoLabels = self.getMedia(item, infoLabels)
        if not self._s.preload_seasons:
            return infoLabels
        c = self._db.cursor()
        asins = infoLabels['asins']
        infoLabels['banner'] = None
        season = int(infoLabels.get('season', -2))
        series = contentType == 'season' and self._s.dispShowOnly
        series_art = season > -1 and self._s.showfanart and self._s.tmdb_art != 0
        extra = ' and season = %s' % season if season > -2 else ''
        for asin in asins.split(','):
            j = None
            result = c.execute('select info from art where asin like (?)' + extra, ('%' + asin + '%',)).fetchone()
            if result:
                j = {k: v for k, v in json.loads(result[0]).items() if v != self._g.na and v is not None}
                if 'poster' in j and contentType != 'episode':
                    infoLabels['thumb'] = j['poster']
                if 'poster' in j and contentType != 'movie':
                    infoLabels['poster'] = j['poster']
                if 'fanart' in j:
                    infoLabels['fanart'] = j['fanart']
                if 'banner' in j:
                    infoLabels['banner'] = j['banner']
                infoLabels.update({k: v for k, v in j.items() if k not in ['poster', 'fanart', 'banner', 'settings', 'title']})
            if (series_art and result) or series and 'seriesasin' in infoLabels:
                result = c.execute('select info from art where asin like (?) and season = -1', ('%' + infoLabels['seriesasin'] + '%',)).fetchone()
                if result:
                    j = {k: v for k, v in json.loads(result[0]).items() if v != self._g.na or v is None}
                    if 'poster' in j and contentType == 'episode':
                        infoLabels['poster'] = j['poster']
                    if 'fanart' in j and series_art:
                        infoLabels['fanart'] = j['fanart']
                    if series:
                        infoLabels.update({k: v for k, v in j.items() if k not in ['poster', 'fanart', 'banner', 'settings', 'title']})
            if j is not None:
                return infoLabels

        if contentType in ['movie', 'seasonslist', 'season']:
            il = {}
            title = infoLabels['title']
            if 'seasonslist' in contentType:
                title = infoLabels['tvshowtitle']
                il = infoLabels if infoLabels['season'] == item['selectedSeason']['seasonNumber'] else {}
            elif 'movie' in contentType:
                il = self.getMedia(item, il)
            c.execute('insert or ignore into miss values (?,?,?,?,?)', (asins, title, infoLabels['year'], contentType, json.dumps(il)))
        c.close()
        self._db.commit()
        return infoLabels

    def processMissing(self):
        Log('Starting Fanart Update')
        infos_updated = False
        container_path = xbmc.getInfoLabel('Container.FolderPath')
        c = self._db.cursor()
        data = ''
        while data is not None:
            data = c.execute('select * from miss limit 1').fetchone()
            if data is not None:
                self.retrieveArtWork(*data)
                c.execute('delete from miss where asins = ?', (data[0],))
                self._db.commit()
                infos_updated = True
        c.close()
        #if container_path == xbmc.getInfoLabel('Container.FolderPath') and infos_updated:
        #    xbmc.executebuiltin('Container.Refresh')
        Log('Finished Fanart Update')

    def retrieveArtWork(self, asins, title, year, contentType, il):
        from .art import Artwork
        item = None
        aw = Artwork()
        il = json.loads(il)
        title = title.lower().replace('?', '').replace('omu', '').split('(')[0].split('[')[0].strip()
        cur = self._db.cursor()

        if not asins:
            return
        if not il:
            item = self.getPage('details', 'itemId=' + asins, -2)
        if item and 'selectedSeason' in item:
            il = self.getInfos(item['selectedSeason'], item, True)
            if len(item.get('seasons', 0)) > 1 and contentType != 'seasonslist' and self._s.preload_all_seasons:
                for season in item['seasons']:
                    s_id = season['titleId']
                    s_num = season['seasonNumber']
                    if s_num != il['season']:
                        result = cur.execute('select asin from art where asin like (?)', ('%' + s_id + '%',)).fetchone()
                        if result is None:
                            cur.execute('insert or ignore into miss values (?,?,?,?,?)', (s_id, il['tvshowtitle'], None, 'season', '{}'))
                self._db.commit()
        il['setting'] = 0
        season_number = il.get('season')

        if contentType == 'movie' and self._s.tmdb_art > 9:
            il['setting'] = self._s.tmdb_art
            il['fanart'] = aw.getTMDBImages(title, year=year)
        if (contentType == 'season' or contentType == 'series') and self._s.tmdb_art > 9:
            il['setting'] = self._s.tmdb_art
            seasons, il['poster'], il['fanart'] = aw.getTVDBImages(title)
            if not il['fanart']:
                il['fanart'] = aw.getTMDBImages(title, content='tv')
            season_number = -1
            content = getATVData('GetASINDetails', 'ASINList=' + asins)['titles']
            if content:
                asins = self.getAsins(content[0], False)
                del content

        if 'season' in contentType and il['season'] == 1:
            s_il = deepcopy(il)
            s_il['title'] = il['tvshowtitle']
            cur.execute('insert or ignore into art values (?,?,?,?)', (il['seriesasin'], -1, json.dumps(s_il), self.days_since_epoch()))
        cur.execute('insert or ignore into art values (?,?,?,?)', (asins, season_number, json.dumps(il), self.days_since_epoch()))
        self._db.commit()
        cur.close()

    @staticmethod
    def getAsins(content, crIL=True):
        infoLabels = {'plot': None, 'mpaa': None, 'cast': [], 'year': None, 'premiered': None, 'rating': None, 'votes': None,
                      'isAdult': 1 if content.get('isAdultContent', False) else 0,
                      'director': None, 'genre': None, 'studio': None, 'thumb': None, 'fanart': None, 'isHD': False, 'isUHD': False,
                      'audiochannels': 1, 'TrailerAvailable': False,
                      'asins': content.get('id', content.get('titleId', content.get('channelId', ''))),
                      'isPrime': content.get('showPrimeEmblem', False)}

        if infoLabels['isPrime'] is False and 'messagePresentation' in content:
            infoLabels['isPrime'] = not len(content['messagePresentation'].get('glanceMessageSlot', []))
        if 'badges' in content:
            b = content['badges']
            infoLabels['isAdult'] = 1 if b.get('adult', True) else 0
            infoLabels['isPrime'] = b.get('prime', True)
            infoLabels['audiochannels'] = 6 if b.get('dolby51', False) else 2
            infoLabels['isUHD'] = b.get('uhd', False)
        if 'playbackActions' in content and len(content['playbackActions']) > 0:
            pa = content['playbackActions'][0]
            infoLabels['isHD'] = pa['userPlaybackMetadata'].get('videoQuality', 'SD') != 'SD'
            infoLabels['isPrime'] = pa['userPlaybackMetadata'].get('consumable', False) is True

        del content
        return infoLabels if crIL else infoLabels['asins']

    def getInfos(self, item, items='', noart=False):
        from datetime import datetime
        item = self.filterDict(item)
        infoLabels = self.getAsins(item)
        if 'channelId' in item:
            return self.getChanInfo(item, infoLabels)
        infoLabels['title'] = self.cleanTitle(item['title'])
        infoLabels['contentType'] = infoLabels['mediatype'] = ct = item['contentType'].lower()
        if items != '':
            infoLabels['tvshowtitle'] = items['show']['title']
            infoLabels['seriesasin'] = items['show']['titleId']
            infoLabels['totalseasons'] = len(items['seasons'])
            infoLabels['season'] = item.get('seasonNumber')
            if ct == 'seasonslist':
                infoLabels['title'] = item['displayText']
                item = items
        if noart is False:
            infoLabels = self.getArtandInfo(infoLabels, ct, item)
        else:
            infoLabels = self.getMedia(item, infoLabels)
        if 'seasonslist' in ct:
            infoLabels['contentType'] = infoLabels['mediatype'] = 'season'
            return infoLabels
        reldate = item.get('publicReleaseDate', item.get('releaseDate', 0))
        reldate = reldate * -1 if reldate < 0 else reldate
        infoLabels['plot'] = item['synopsis']
        infoLabels['isAdult'] = 1 if item.get('isAdultContent', False) else 0
        infoLabels['votes'] = item.get('amazonRatingsCount', 0)
        infoLabels['premiered'] = datetime.fromtimestamp(reldate / 1000).strftime('%Y-%m-%d')
        infoLabels['genre'] = item.get('genres')
        infoLabels['studio'] = item.get('studios')
        if item.get('runtimeMillis'):
            infoLabels['duration'] = item['runtimeMillis'] / 1000
        if item.get('runtimeSeconds'):
            infoLabels['duration'] = item['runtimeSeconds']
        if 'season' in ct and 'tvshowtitle' in infoLabels and self._s.dispShowOnly and noart is False:
            infoLabels['title'] = infoLabels['tvshowtitle']
            infoLabels['plot'] = '{}\n\n{}'.format(getString(30253).format(infoLabels['totalseasons']), infoLabels['plot'])
        if 'episode' in ct:
            infoLabels['episode'] = item['episodeNumber']
            infoLabels['season'] = item['seasonNumber']
        if infoLabels['votes'] > 0:
            infoLabels['rating'] = item.get('amazonAverageRating', 1) * 2
        if 'regulatoryRating' in item:
            if item['regulatoryRating'] == 'not_checked' or not item['regulatoryRating']:
                infoLabels['mpaa'] = getString(30171)
            else:
                infoLabels['mpaa'] = '%s %s' % (AgeRestrictions().GetAgeRating(), item['regulatoryRating'])
        if 'live' in ct:
            infoLabels['contentType'] = infoLabels['mediatype'] = 'videos'
            infoLabels['isPrime'] = True
        return infoLabels

    def getMedia(self, item, infoLabels):
        media = {'fanart': {'': ['detailPageHeroImageUrl'],
                            'titleImageUrls': ['WIDE', 'WIDE_PRIME', 'COVER', '']},
                 'thumb': {'': ['titleImageUrl'],
                           'titleImageUrls': ['LEGACY', 'LEGACY_PRIME', 'BOX_ART', '']},
                 'poster': {'titleImageUrls': ['POSTER']}
                 }
        for il, i in media.items():
            for k, v in i.items():
                dic = item if k == '' else item.get(k, {})
                for m in v:
                    if m in dic and dic[m] is not None and dic[m].strip() != '':
                        infoLabels[il] = self.cleanIMGurl(dic[m])
                        break
        return infoLabels

    def getChanInfo(self, item, infoLabels):
        infoLabels['contentType'] = 'live'
        infoLabels['DisplayTitle'] = infoLabels['title'] = self.cleanTitle(item['channelTitle'])
        infoLabels['thumb'] = self.cleanIMGurl(item.get('channelImageUrl'))
        infoLabels['plot'] = ''
        infoLabels['isPrime'] = True
        shedule = item.get('schedule')
        upnext = False
        if shedule:
            from datetime import datetime
            ts = time.time()
            for sh in shedule:
                us = sh.get('startTime') / 1000
                ue = sh.get('endTime') / 1000
                if (us <= ts <= ue) or upnext:
                    tm = self.filterDict(sh['titleModel'])
                    infoLabels['plot'] += '[B]{:%H:%M} - {:%H:%M}  {}[/B]\n'.format(datetime.fromtimestamp(us), datetime.fromtimestamp(ue), tm.get('title', ''))
                    if not upnext:
                        imgurls = tm.get('titleImageUrls', {})
                        reldate = tm.get('publicReleaseDate', tm.get('releaseDate', 0))
                        reldate = reldate * -1 if reldate < 0 else reldate
                        infoLabels['premiered'] = datetime.fromtimestamp(reldate / 1000).strftime('%Y-%m-%d')
                        infoLabels['fanart'] = self.cleanIMGurl(item.get('channelImageUrl'))
                        infoLabels['thumb'] = self.cleanIMGurl(imgurls.get('LEGACY', imgurls.get('LEGACY_PRIME', item.get('titleImageUrl', imgurls.get('WIDE')))))
                        infoLabels['plot'] += '{}\n\n'.format(tm.get('synopsis', ''))
                        if item.get('runtimeMillis'):
                            infoLabels['duration'] = tm['runtimeMillis'] / 1000
                    else:
                        break
                    upnext = True
        return infoLabels

    @staticmethod
    def filterDict(d):
        # remove None value keys from dict
        d_filt = {k: v for k, v in d.items() if v is not None}
        return d_filt

    @staticmethod
    def cleanIMGurl(img):
        # r'\.[^/]+(\.[^/]+$)', '\\1'
        return re.sub(r'\._.*_\.', r'.', img) if img else None

    def getProfiles(self):
        resp = self.getPage('profiles')
        if not resp:
            return False, False
        profiles = []
        active = 0
        for item in resp['profiles']:
            n = item.get('name', 'Default').encode('utf-8')
            profiles.append((n, item['profileId'], item['avatar']['avatarUrls']['round']))
            if item.get('isActive', False):
                active = len(profiles) - 1
                writeConfig('profileID', '' if item.get('isDefault', False) else n)
        return active, profiles

    def switchProfile(self):
        active, profiles = self.getProfiles()
        if active is not False:
            ret = self._g.dialog.select('Amazon', [i[0] for i in profiles])
            if ret >= 0 and ret != active:
                if refreshToken(loadUser(), profiles[ret][1]):
                    exit()

    def languageselect(self):
        loc, lang = LocaleSelector()
        resp = getURL('{}/lps/setDevicePreferredLanguage/v1?'
                      'deviceTypeID={}'
                      '&firmware=fmw%3A22-app%3A3.0.340.20045'
                      '&priorityLevel=2'
                      '&format=json'
                      '&deviceID={}'
                      '&locale={}&osLocale={}&uxLocale={}'
                      '&version=1'
                      '&preferenceType=IMPLICIT'.format(self._g.ATVUrl, self.def_dtid, g.deviceID, loc, loc, loc), headers=self._g.headers_android, postdata='')
        if resp.get('success', False):
            updateUser('lang', loc)
            Log('Text language changed to [{}] {}'.format(loc, lang), Log.DEBUG)

    def Route(self, mode, args):
        if mode == 'Search':
            searchString = args.get('searchstring')
            self.Search(searchString)
        elif mode in ['processMissing', 'switchProfile', 'languageselect']:
            exec ('g.pv.{}()'.format(mode))
        elif mode == 'ageSettings':
            AgeRestrictions().Settings()
        elif mode == 'getPage':
            self.getPage(args.get('url'), args.get('opt', ''), int(args.get('page', '1')))
        elif mode == 'editWatchList':
            self.editWatchList(args.get('url', ''), int(args.get('opt', '0')))
