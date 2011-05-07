# -*- coding: utf-8 -*

import re
import string
from show import *
from common import *
from episode import *

# Initializer called by the framework
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - 
def Start():
    Plugin.AddPrefixHandler(PLUGIN_PREFIX, MainMenu, TEXT_TITLE, "icon-default.png", "art-default.jpg")
    HTTP.CacheTime = CACHE_TIME_SHORT
    HTTP.PreCache(URL_INDEX)
    MediaContainer.art = R(ART)
    
    #Create thread to reindex shows in the background
    #Thread.Create(ReindexShows, MAX_PAGINATE_PAGES)
    Log("Quality Setting: %s" % Prefs[PREF_QUALITY])

# Menu builder methods
# - - - - - - - - - - - - - - - - - - - - - - - - - - - -
def MainMenu():
    menu = MediaContainer(viewGroup="List", title1= TEXT_TITLE + " " + VERSION)
    menu.Append(Function(DirectoryItem(GetIndexShows, title=TEXT_INDEX_SHOWS, thumb=R('main_index.png'))))
    #menu.Append(Function(DirectoryItem(ListLiveMenu, title=LIVE_SHOWS, thumb=R('main_live.png'))))
    menu.Append(PrefsItem(u"Inställningar"))
    return menu

def ListLiveMenu(sender):
    showsList = MediaContainer()
    liveElements = HTML.ElementFromURL(LIVE_URL)
    for element in liveElements.xpath("//span[@class='thumbnail']//a[@class='tableau']"):
        liveName = strip_all(unicode(element.xpath("../../../../h3/text()")[0]))        
        Log("LiveName: %s" % liveName)
        liveUrl = SITE_URL +  element.get("href")
       
        # Get the actual stream url from subpage and do some munging for the plex player to get it
        liveContentUrl = GetEpisodeInfo(liveUrl)[2]
        liveContentUrl = re.sub(r'^(.*)/(.*)$','\\1&clip=\\2', liveContentUrl)
        liveContentUrl = PLEX_PLAYER_URL + liveContentUrl +"&live=true&width=640&height=360"
       
        Log("Live content url: " + liveContentUrl)
        liveIcon= element.xpath("descendant::img[starts-with(@class, 'thumbnail')]")[0].get("src")
        liveDesc = strip_all(unicode(element.xpath("../../span[@class='description']/text()")[0]))
        Log("Live icon % s" % liveIcon)
        Log("LiveDesc: %s" % liveDesc)
        showsList.Append(WebVideoItem(url=liveContentUrl, title=liveName, summary=liveDesc, duration="0", thumb=liveIcon))
        
    return showsList 

# Main method for sucking out svtplay content
def BuildGenericMenu(url, divId):
    menuItems = []
    pageElement = HTML.ElementFromURL(url)
    Log("url: %s divId: %s" % (url, divId))
    xpathBase = "//div[@id='%s']" % (divId)
    Log("xpath expr: " + xpathBase)

    clipLinks = pageElement.xpath(xpathBase + "//a[starts-with(@href,'/v/')]")
    for clipLink in clipLinks:
        clipName = clipLink.xpath("span/text()")[0].strip()
        Log("Clip : %s" % (clipName.encode('utf8')))
        clipUrl = SITE_URL + clipLink.get("href")
        Log("URL: " + clipUrl)
        clipIcon = clipLink.xpath("img")[0].get("src").replace("_thumb","_start")
        Log("Clip icon: >" + clipIcon + "<")
        (clipSummary, clipLength, contentUrl) = GetEpisodeInfo(clipUrl) 
        if (contentUrl.endswith('.flv')):
            v = VideoItem(key=contentUrl, title=clipName, summary=clipSummary, duration=clipLength,thumb=clipIcon)
            menuItems.append(v)
        else:
            # should be rtmp url
            if (contentUrl.endswith('.mp4')):
               #special case rmpte stream with mp4 ending.
               contentUrl = PLEX_PLAYER_URL + contentUrl.replace("_definst_/","_definst_&clip=mp4:")
            else:
                contentUrl = PLEX_PLAYER_URL + contentUrl.replace("_definst_/","_definst_&clip=")
            menuItems.append(Function(VideoItem(PlayVideo, clipName, summary=clipSummary, thumb=clipIcon, duration=clipLength), url=contentUrl))
        
    # Note: must have "span" element, otherwise some wierd stuff can come along...
    programLinks = pageElement.xpath(xpathBase + "//a[starts-with(@href, '/t/')]/span/..")
    for programLink in programLinks:
        programName = programLink.xpath("span/text()")[0].strip()
        Log("Program : %s" % (programName.encode('utf8')))
        programUrl = SITE_URL + programLink.get("href")
        programIcon = programLink.xpath("img")[0].get("src") #GetHiResIconFromSubPage(programUrl)
        programSummary = GetProgramInfo(programUrl)
        menuItems.append(Function(DirectoryItem(ListShowEpisodes, programName, summary=programSummary, thumb=programIcon), showName = programName, showUrl = programUrl))

    # Subcategories (used in "Bolibompa" and maybe more)
    subCategoryLinks = pageElement.xpath(xpathBase + "//a[@class='folder overlay tooltip']/span/..")
    for subCategoryLink in subCategoryLinks:
        subCategoryName = subCategoryLink.xpath("span/text()")[0].strip()
        subCategoryUrl = url + subCategoryLink.get("href")
        subCategoryImage = subCategoryLink.xpath("img[@class='folder-thumb']")[0].get("src")
        menuItems.append(Function(DirectoryItem(key=HierarchyDown, title=subCategoryName, thumb=subCategoryImage), url=subCategoryUrl, baseUrl=url, divId = divId))

    return menuItems
    
def PlayVideo(sender, url):
    Log("Request to play video: %s" % url)
    return Redirect(WebVideoItem(url))


def HierarchyDown(sender, url, baseUrl, divId):
    Log("HD: %s" % url)
    menu = MediaContainer()
    paginateUrl = FindPaginateUrl(url)
    paginateUrl = baseUrl + paginateUrl
    menu.Extend(Paginate(paginateUrl % 1, paginateUrl, divId, BuildGenericMenu))

    return menu


# Helpers
# - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    
def GetProgramInfo(programUrl):
    programHtml = HTTP.Request(url=programUrl, cacheTime=CACHE_TIME_LONG)
    infoElements = HTML.ElementFromString(programHtml).xpath("//div[@id='description-title']")
    if (len(infoElements) > 0):
        return infoElements[0].text.strip()
    return NO_INFO
     
   
def GetContentUrl(pageElement):
    flashvars = pageElement.xpath("//object[@id='playerSwf']/param[@name='flashvars']")[0].get("value")
    
    #If it's an rtmp stream, try to find the different qualities
    if(flashvars.find("rtmp") > -1):
        d = GetUrlQualitySelection(flashvars)
        try: 
            url = d[Prefs['quality']]
        except KeyError:
            url = d[QUAL_T_HIGHEST]
        Log("Url selection: %s" % url) 
        return url 
    else:
        Log("Flashvars not found! Using first found stream")
    
    return re.search(r'(pathflv=|dynamicStreams=url:)(.*?)[,&$]',flashvars).group(2)    

def GetUrlQualitySelection(flashvars):
    #You could make this more sophisticated by checking that the link you select also
    #match the correct bitrate and not just assume they are in descending order
    Log("flashvars: %s" % flashvars)
    links = re.findall("rtmp.*?,", flashvars)

    cleanLinks = [link.replace(',','') for link in links]
    links = cleanLinks
    d = dict()
    d[QUAL_T_HIGHEST] = links[0]
    d[QUAL_T_HD] = links[0]
    Log("Dict len: %d" % len(links))
    if(len(links) > 1):
        d[QUAL_T_HIGH] = links[1]
    if(len(links) > 2):
        d[QUAL_T_MED] = links[2]
    if(len(links) > 3):
        d[QUAL_T_LOW] = links[3]

    Log(d)
    return d
    
# Replaces all running whitespace characters with a single space
def strip_all(str):
    return string.join(string.split(str), ' ')
    

        
