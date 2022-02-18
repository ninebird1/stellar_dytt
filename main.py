from operator import le
import threading
import time
import bs4
import requests
import StellarPlayer
import re
import urllib.parse

dytt_url = 'https://www.dydytt.net/index2.htm'

def concatUrl(url1, url2):
    splits = re.split(r'/+',url1)
    url = splits[0] + '//'
    if url2.startswith('/'):
        url = url + splits[1] + url2
    else:
        url = url + '/'.join(splits[1:-1]) + '/' + url2
    return url

#爬取影视页面中的播放链接地址
def parse_dytt_movie(url):
    res = requests.get(url,verify=False)
    if res.status_code == 200:
        bs = bs4.BeautifulSoup(res.content.decode('gb2312','ignore'),'html.parser')
        selector = bs.select('#Zoom > span a')
        print(selector)
        for item in selector:
            return item.get('href')
    else:
        print(res.text)

def parse_dytt_movie_and_pic(url):
    print(f'parse_dytt_movie_and_pic:{url=}')
    res = requests.get(url,verify=False)
    obj = {}
    if res.status_code == 200:
        bs = bs4.BeautifulSoup(res.content.decode('gb2312','ignore'),'html.parser')
        selector = bs.select('#Zoom > span a')
        for item in selector:
            obj['movie'] = item.get('href')
        selector = bs.select('#Zoom > span img')
        for item in selector:
            obj['pic'] = item.get('src')
    else:
        print(res.text)
    print(obj)
    return obj

#爬取某个分类页面的所有影视页面链接
def parse_dytt_page_movies(page_url):
    urls = []
    res = requests.get(page_url,verify=False)
    if res.status_code == 200:
        bs = bs4.BeautifulSoup(res.content.decode('gb2312','ignore'),'html.parser')
        selector = bs.select('#header > div > div.bd2 > div.bd3 > div.bd3r > div.co_area2 > div.co_content8 > ul')
        for ul in selector:
            for item in ul.select('table a'):
                url = concatUrl(page_url,item.get('href'))
                title = ''
                #普通页面的情况
                if item.string:
                    if not re.match(r'\[(\w+)\]', item.string):
                        title = item.string
                #搜索页面情况
                else:
                    for nav_str in item.children:
                        if nav_str.string:
                            title = title + nav_str.string
                if title:
                    urls.append({'title':title,'url':url})
    else:
        print(res.text)
    return urls

#爬取分类对应的所有页面数
def parse_dytt_page_num(pageUrl):
    print(pageUrl)
    pages = []
    res = requests.get(pageUrl,verify=False)
    if res.status_code == 200:
         bs = bs4.BeautifulSoup(res.content.decode('gb2312','ignore'),'html.parser')
         selector = bs.select('#header > div > div.bd2 > div.bd3 > div.bd3r > div.co_area2 > div.co_content8 > div  select')
         for item in selector:
             for child in item.children:
                 if type(child) == bs4.element.Tag:
                    page = child.get('value')
                    if page:
                        pages.append(page)
    else:
        print(res.text)
    return pages

#爬取所有分类
def parse_dytt_category():
    urls = []
    search_urls = []
    blacks = ['经典影片','旧版游戏','游戏下载','收藏本站','APP下载']
    res = requests.get(dytt_url,verify=False)
    if res.status_code == 200:
        bs = bs4.BeautifulSoup(res.content.decode('gb2312','ignore'), 'html.parser')
        selector = bs.select('#menu > div > ul > li')
        print(selector)
        for item in selector:
            for child in item.children:
                if type(child) == bs4.element.Tag:
                    url = child.get('href')
                    if url:
                        if not re.match(r'http',url):
                            url = concatUrl(dytt_url, url)
                        if not child.string in blacks:
                            urls.append({'title':child.string,'url':url})
        #获取搜索页面链接
        selector = bs.select('#header > div > div.bd2 > div.bd3 > div:nth-child(2) > div:nth-child(1) > div > div.search > form > div.searchl > p:nth-child(1) > select')
        for item in selector:
            for child in item.children:
                if type(child) == bs4.element.Tag:
                    search_urls.append({'title':child.string,'url':child.get('value')})
    return urls, search_urls

class dyttplugin(StellarPlayer.IStellarPlayerPlugin):
    def __init__(self,player:StellarPlayer.IStellarPlayer):
        super().__init__(player)
        self.categories = []
        self.search_urls = []
        self.pages = []
        self.movies = []
        self.pageIndex = 0
        self.curCategory = ''
        self.cur_page = '第' + str(self.pageIndex + 1) + '页'
        self.num_page = ''
        self.search_word = ''
        self.search_movies = []
        self.detail_urls = []
        self.gbthread = threading.Thread(target=self._bgThread)

    def _bgThread(self):
        while len(self.categories) == 0 and not self.isExit:
            self.parsePage()
            time.sleep(0.001)
        print(f'dytt bg thread:{self.gbthread.native_id} exit')
        # 刷新界面
        def update():
            if self.player.isModalExist('main'):
                self.updateLayout('main',self.makeLayout())
                self.loading(True)
        if hasattr(self.player,'queueTask'):
            self.player.queueTask(update)
        else:
            update()
       
    def stop(self):
        if self.gbthread.is_alive():
            print(f'dytt bg thread:{self.gbthread.native_id} is still running')
        return super().stop()

    def start(self):
        self.gbthread.start()
        return super().start()

    def parsePage(self):
        #获取分类导航
        if len(self.categories) == 0:
            self.categories, self.search_urls = parse_dytt_category()
        if len(self.categories) > 0:
            if not self.curCategory:
                self.curCategory = self.categories[0]['url']
            #获取该分类的所有页面数
            if len(self.pages) == 0:
                self.pages = parse_dytt_page_num(self.curCategory)
                self.num_page = '共' + str(len(self.pages)) + '页'
                if len(self.pages) > 0:
                    #获取分页视频资源
                    if len(self.movies) == 0:
                        url = concatUrl(self.curCategory, self.pages[self.pageIndex])
                        self.movies = parse_dytt_page_movies(url)  

    def makeLayout(self):
        nav_labels = []
        for cat in self.categories:
            nav_labels.append({'type':'link','name':cat['title'],'@click':'onCategoryClick'})

        list_layout = [
                            {'type':'label','name':'title'},
                            {'type':'link','name':'详情','width':30,'@click':'onDetailClick'},
                            {'type':'space','width':10},
                            {'type':'link','name':'播放','width':30,'@click':'onPlayClick'},
                      ]
        if hasattr(self.player,'download'):
            list_layout.append({'type':'space','width':10})
            list_layout.append({'type':'link','name':'下载','width':30,'@click':'onDownloadClick'})

        controls = [
            {'group':nav_labels,'height':30},
            {'type':'space','height':10},
            {'group':
                [
                    {'type':'edit','name':'search_edit','label':'搜索'},
                    {'type':'button','name':'搜电影','@click':'onSearch'}
                ]
                ,'height':30
            },
            {'type':'space','height':10},
            {'type':'list','name':'list','itemlayout':{'group':list_layout},'value':self.movies,'separator':True,'itemheight':40},
            {'group':
                [
                    {'type':'space'},
                    {'group':
                        [
                            {'type':'label','name':'cur_page',':value':'cur_page'},
                            {'type':'link','name':'上一页','@click':'onClickFormerPage'},
                            {'type':'link','name':'下一页','@click':'onClickNextPage'},
                            {'type':'link','name':'首页','@click':'onClickFirstPage'},
                            {'type':'link','name':'末页','@click':'onClickLastPage'},
                            {'type':'label','name':'num_page',':value':'num_page'},
                        ]
                        ,'width':0.45
                        ,'hAlign':'center'
                    },
                    {'type':'space'}
                ]
                ,'height':30
            },
            {'type':'space','height':5}
        ]
        return controls
        
    def show(self):
        controls = self.makeLayout()
        self.doModal('main',800,600,'',controls)

    def onModalCreated(self, pageId):
        print(f'dytt onModalCreated {pageId=}')
        if pageId == 'main':
            if len(self.movies) == 0:
                self.loading()
        elif pageId != 'search':
            self.loadingPage(pageId)

    def onSearchInput(self,*args):
        print(f'{self.search_word}')

    def onSearch(self,*args):
        self.search_word = self.player.getControlValue('main','search_edit')
        if len(self.search_urls) > 0:
            url = self.search_urls[0]['url'] + urllib.parse.quote(self.search_word,encoding='gbk')
            print(f'url={url}')
            self.search_movies = parse_dytt_page_movies(url)
            if len(self.search_movies) > 0:
                list_layout = {'group':[{'type':'label','name':'title','width':0.9},{'type':'link','name':'播放','width':30,'@click':'onPlayClick'},{'type':'space'}]}
                controls = {'type':'list','name':'list','itemlayout':list_layout,'value':self.search_movies,'separator':True,'itemheight':40}
                if not self.player.isModalExist('search'):
                    self.doModal('search',500,400,self.search_word,controls)
                else:
                    self.player.updateControlValue('search','list',self.search_movies)
            else:
                self.player.toast('main',f'没有找到 {self.search_word} 相关的资源')
    

    def onCategoryClick(self,pageId,control,*args):
        for cat in self.categories:
            if cat['title'] == control:
                if cat['url'] != self.curCategory:
                    self.curCategory = cat['url']
                    self.pageIndex = 0
                    #获取新分类的页面数
                    self.loading()
                    self.pages = parse_dytt_page_num(self.curCategory)
                    self.num_page = num_page ='共' + str(len(self.pages)) + '页'
                    self.player.updateControlValue('main','num_page',num_page)
                    self.selectPage()
                    self.loading(True)
                break
        
    def onPlayClick(self, pageId, control, item, *args):
        if pageId == 'main':
            playUrl = parse_dytt_movie(self.movies[item]['url'])
        elif pageId == 'search':
            playUrl = parse_dytt_movie(self.search_movies[item]['url'])
        if playUrl:
            self.player.play(playUrl)

    def onDownloadClick(self, pageId, control, item, *args):
        if pageId == 'main':
            playUrl = parse_dytt_movie(self.movies[item]['url'])
        elif pageId == 'search':
            playUrl = parse_dytt_movie(self.search_movies[item]['url'])
        if playUrl:
            self.player.download(playUrl)

    def onDetailClick(self, pageId, control, item, *args):
        url = self.movies[item]['url']
        title = self.movies[item]['title']
        print(url)
        def parse_dytt_detail():
            res = requests.get(url,verify=False)
            if res.status_code == 200:
                controls = []
                bs = bs4.BeautifulSoup(res.content.decode('gb2312','ignore'),'html.parser')
                #解析图片
                selector = bs.select('#Zoom > span  img')
                for item in selector:
                    controls.append({'type':'image','value':item.get('src'),'width':200,'height':300})

                #解析简介
                skip = False
                selector = bs.select('#Zoom > span > td')
                for item in selector:
                    for br in item.children:
                        if not br.string:
                            continue
                        href = None
                        if type(br) == bs4.element.Tag:
                            href = br.get('href')
                        if not re.match(r'主演|导演|演员|编剧',re.sub(r'\W+','',br.string)) or href:
                            if re.match(r'标签|简介',re.sub(r'\W+','',br.string)):
                                skip = False
                            if not skip or href:
                                if type(br) == bs4.element.NavigableString:
                                    controls.append({'type':'label','value':br.string,'height':20})
                                elif href:
                                    controls.append({'type':'link','name':br.string,'height':30,'@click':'on_detail_page_play'})
                                     #保存页面对应的详情播放地址
                                    self.detail_urls.append({'title':title,'url':href})
                        else:
                            skip = True
                
                def update_detail_ui():
                    self.loadingPage(title, True)
                    self.updateLayout(title, controls)
                   
                if hasattr(self.player,'queueTask'):
                    self.player.queueTask(update_detail_ui)
                else:
                    update_detail_ui()

        t = threading.Thread(target=parse_dytt_detail)
        t.start()
        self.doModal(title, 600, 800, title, [])
        #删除详情播放地址
        for item in self.detail_urls:
            if item['title'] == url:
                self.detail_urls.remove(item)
                break

    def on_detail_page_play(self,pageId, *args):
         for item in self.detail_urls:
            if item['title'] == pageId:
                self.player.play(item['url'])
                break

    def selectPage(self):
        if len(self.pages) > self.pageIndex:
                self.movies.clear()
                self.player.updateControlValue('main','list',self.movies)
                url = concatUrl(self.curCategory, self.pages[self.pageIndex])
                self.movies = parse_dytt_page_movies(url)
                self.player.updateControlValue('main','list',self.movies)
                self.cur_page = cur_page = '第' + str(self.pageIndex + 1) + '页'
                self.player.updateControlValue('main','cur_page',cur_page)

    def onClickFormerPage(self, *args):
        if self.pageIndex > 0:
            self.pageIndex = self.pageIndex - 1
            self.loading()
            self.selectPage()
            self.loading(True)

    def onClickNextPage(self, *args):
        num_page = len(self.pages)
        if self.pageIndex + 1 < num_page:
            self.pageIndex = self.pageIndex + 1
            self.loading()
            self.selectPage()
            self.loading(True)

    def onClickFirstPage(self, *args):
        if self.pageIndex != 0:
            self.pageIndex = 0
            self.loading()
            self.selectPage()
            self.loading(True)

    def onClickLastPage(self, *args):
        if self.pageIndex != len(self.pages) - 1:
            self.pageIndex = len(self.pages) - 1
            self.loading()
            self.selectPage()
            self.loading(True)

    def loading(self, stopLoading = False):
        if hasattr(self.player,'loadingAnimation'):
            self.player.loadingAnimation('main', stop=stopLoading)

    def loadingPage(self, page, stopLoading = False):
        if hasattr(self.player,'loadingAnimation'):
            self.player.loadingAnimation(page, stop=stopLoading)

    def onPlayerSearch(self, dispatchId, searchId, wd, limit):
        # 播放器搜索异步接口
        print(f'onPlayerSearch:{wd}')
        result = []
        if len(self.search_urls) > 0:
            url = self.search_urls[0]['url'] + urllib.parse.quote(wd,encoding='gbk')
            print(f'url={url}')
            movies = parse_dytt_page_movies(url)
            for item in movies:
                mov = parse_dytt_movie_and_pic(item['url'])
                if mov.get('movie'):
                    magnet = mov['movie']
                    pic_url = mov.get('pic', None)
                    if magnet.startswith('magnet'):
                        result.append({'name':item['title'],'urls':[['磁力',magnet]],'pic':pic_url})
                if len(result) >= limit:
                    break
        self.player.dispatchResult(dispatchId, searchId=searchId, wd=wd, result=result)
    
def newPlugin(player:StellarPlayer.IStellarPlayer,*arg):
    plugin = dyttplugin(player)
    return plugin

def destroyPlugin(plugin:StellarPlayer.IStellarPlayerPlugin):
    plugin.stop()
