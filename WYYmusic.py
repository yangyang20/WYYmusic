from requests.exceptions import ReadTimeout, ConnectionError, RequestException
import time
from concurrent.futures import ProcessPoolExecutor,ThreadPoolExecutor
import requests
from multiprocessing import Manager
import pymongo
import pymysql
import re
from bs4 import BeautifulSoup
# from config import *

headers ={
    'User-Agent':'Mozilla/5.0 (Windows NT 6.3; WOW64; rv:41.0) Gecko/20100101 Firefox/41.0',
    'X-Requested-With':'XMLHttpRequest',
    'Connection': 'close'
}

session = requests.session()
# 避免连接太多没有关闭导致socket超时
session.keep_alive = False
# 歌曲信息
songDdetails = {}
# 歌手信息
singerInformation ={}
# 歌手分类
singerClassify = {}
# mysql数据库信息
conn = pymysql.connect(host='127.0.0.1', user='root', password="393622951", db='WangYiYun')
cur = conn.cursor()

# 获取歌手分类的id
def singClassifyList():
    url = 'https://music.163.com/discover/artist'
    try:
        response = session.get(url=url,headers=headers,timeout=3)
        soup = BeautifulSoup(response.text,"html5lib")
        classify = soup.select(".cat-flag")
        singClassifyIdArr = []
        for item in classify:
            href = item['href']
            # 解析出歌手分类名称的id
            singClassifyId = str(re.findall(r'id=(\d{4})', href))[2:-2]
            if singClassifyId:
                singClassifyIdArr.append(singClassifyId)
                # 歌手分类名称,此处暂未用到
                singerClassify[singClassifyId] = item.string
        # 调用多进程爬取不同分类
        myProcess(singClassifyIdArr)
    except ReadTimeout:  # 访问超时的错误
        print('singClassifyList Timeout')
        print(url)
        return None
    except ConnectionError:  # 网络中断连接错误
        requests.status_code = "Connection refused"
        print('singClassifyList Connect error')
        print(url)
        return None
    except RequestException:  # 父类错误
        print('singClassifyList Error')
        print(url)
        return None



# 多进程爬取分类
def myProcess(singClassifyIdArr):
    with ProcessPoolExecutor(max_workers=len(singClassifyIdArr)) as executor:
            for i in singClassifyIdArr:
                # 多进程之间不能共享全局变量
                executor.submit(myThread, i)
                # continue
                break

# 多线程爬取分类下的分页
def myThread(singId):
    with ThreadPoolExecutor(max_workers=26) as thread:
        for i in range(65,90):
            # 创建26个线程，分别执行A-Z分类
            thread.submit(singList, singId,i)
            break



# 获取所有的歌手的id
def singList(singClassifyId,id):
    url = 'https://music.163.com/discover/artist/cat?id=%s&initial=%s' % (singClassifyId, id)
    while True:
        try:
            response = session.get(url=url,headers=headers,timeout=3)
            soup = BeautifulSoup(response.text,"html5lib")
            # 歌手分类名称与分类ID
            singerInformation['singClassifyId'] = singClassifyId;
            singerInformation['singerClassify'] = soup.select('.d-flag')[0].string
            singList = soup.select('.nm-icn')
            for item in singList:
                # 歌手名称
                text = item.string
                href = item['href']
                # 解析出的歌手id
                id = str(re.findall(r'id=(\d+)',href))[2:-2]
                songDdetails['singer'] = text
                singerInformation['singer'] = text
                # 以歌手的id为索引,方便查歌曲信息
                singerInformation['singId'] = int(id)
                songDdetails['singId'] = int(id)
                # insert_mysql()
                singerPopularSong(id)
                continue
            break
        except ReadTimeout:  # 访问超时的错误
            print('singList Timeout')
            print(url)
            time.sleep(1)
            # return None
        except ConnectionError:  # 网络中断连接错误
            requests.status_code = "Connection refused"
            print('singList Connect error')
            print(url)
            time.sleep(1)
            # return None
        except RequestException:  # 父类错误
            print('singList Error')
            print(url)
            return None



# 获取每个歌手热门歌曲的id
def singerPopularSong(id):
    url = 'https://music.163.com/artist?id=%s' % id
    while True:
        try:
            response = session.get(url=url,headers=headers,timeout=3)
            soup = BeautifulSoup(response.text,"html5lib")
            a = soup.select("ul.f-hide a")
            for item in a:
                href = item['href']
                text = item.text
                songDdetails['songName'] = text
                # 将链接中的歌曲id解析出来
                songDdetails['_id'] = str(re.findall(r'id=(\d+)',href))[2:-2]
                download(songDdetails['_id'])
                continue
            break
        except ReadTimeout:  # 访问超时的错误
            print('singerPopularSong Timeout')
            print(url)
            time.sleep(1)
            # return None
        except ConnectionError:  # 网络中断连接错误
            requests.status_code = "Connection refused"
            print('singerPopularSong Connect error')
            print(url)
            time.sleep(1)
            # return None
        except RequestException:  # 父类错误
            print('singerPopularSong Error')
            print(url)
            return None



# 获取所有的榜单id
def rankingList():
    url = 'https://music.163.com/discover/toplist'
    response = session.get(url=url,headers=headers)
    soup = BeautifulSoup(response.text, "html5lib")
    # 获取所有的class为avatar的a标签
    avatar = soup.select('.avatar')
    for item in avatar:
        href = item['href']
        # print(id)
        songList(href)


# 云音乐榜单抓取,url中不能有#号,才是框架源码
def songList(href):
    url = 'https://music.163.com%s' % href
    response = session.get(url=url,headers=headers)
    soup = BeautifulSoup(response.text, "html5lib")
    # 网页数据在<textarea>标签内,先获取到所有歌曲的数据
    songList = soup.find('textarea',id='song-list-pre-data').get_text()
    # 网页数据为字符串,一个列表包含许多歌曲信息的对象
    # 对象内有许多名称相同的key,没有找到较好的转换为json对象的方式
    # 只能正则表达式匹配歌手,歌名,歌曲id信息
    songList = re.findall(r'artists":\[(.*?\d{10}[}|,])',songList)
    for index,item in enumerate(songList):
        # 有些字符串结尾是,先将其转换为}
        if item.endswith('}') == False:
            item = re.sub(r',$','}',item)
        # 匹配到所有的name值,
        nameList = re.findall(r'"name":"(.*?)",',item)
        # 以第一个name值为歌手
        songDdetails['singer'] = nameList[0]
        # 以最后一个name值为歌曲名
        songDdetails['songName'] = nameList[-1]
        # 匹配歌曲的id值
        idList = re.findall(r',"id":(\d+)}',item)
        # 由于名为id的key有重复,如果匹配到多次,取最后一个id的值
        if len(idList)>1:
            songDdetails['_id'] = str(idList[-1])
        songDdetails['_id'] = str(idList)
        songDdetails['_id'] = songDdetails['_id'][2:-2]
        if songDdetails['_id']:
            # len(idList)这个判断总是出现遗漏,再次排除多id的情况
            if len(songDdetails['_id'])>10:
                songDdetails['_id'] = re.findall(r',\'(\d+)',songDdetails['_id'])
            print(songDdetails['_id'])
            download(songDdetails['_id'])
        else:
            print('为空')


# 我的喜欢歌曲列表,此处参数特点还不明确,可以获得歌曲信息
def songMessage():
    url = 'https://music.163.com/weapi/v3/playlist/detail?csrf_token=75097dfb0b9d61d1a7c8eae8e191bef0'
    datas = {
        'params': 'UiQeYTPku7HXOqfZ++LRrTy5tNd1brm0Vznvn63eIIUwKpG63kTbfqHIyZDLrXlCMU8UupHfWhnjeTT61IMarmYU4oBpUGsFZqcNupx2S9hp2NQr1/ZK7mPYYI+Wd2AkK2iyTYiulWVt83d6h5LTpYgooIP9+P4KM5FaunBQZt6YLX+tP/yQKyWKa+wGddghN0ZPwNlyfX4LQYermdAOqmueKbiaNg3J0cd7G9GxSik=',
        'encSecKey': 'd691207d35dc3f4a8dd67ee722232f4fe2e20db553f83c4c037c90772d88e8cde3d9188458a3b9398899d61796cc4f4e09d0176da5ec579fe9761ae4ea65b9c64235535a8eb758578fe3f29dd1ca5f4ef16581172996e365233313ee6cf0f386bd04d061660c38b61f9c714a9893c9c415cb8d28709a0616f3a9f06e1b850f01'
    }
    response = session.post(url=url, headers=headers, data=datas)
    tracks = response.json()['playlist']['tracks']
    for track in tracks:
        songDdetails['songName'] = track['name']
        songDdetails['singer'] = track['ar'][0]['name']
        songDdetails['Album'] = track['al']['name']
        songDdetails['picUrl'] = track['al']['picUrl']
        songDdetails['_id'] = track['id']
        download(songDdetails['_id'])



# 根据歌曲的id值下载歌曲
def download(id):
    url = 'http://music.163.com/song/media/outer/url?id=%s.mp3' % id
    songDdetails['downloadURL'] = url
    while True:
        try:
            response = session.get(url=url,headers=headers,timeout = 5)
            if response.status_code == 200:
                writeDetails(id)
                break
            else:
                return None
        except ReadTimeout:  # 访问超时的错误
            print('download Timeout')
            print(url)
            time.sleep(1)
            # return None
        except ConnectionError:  # 网络中断连接错误
            requests.status_code = "Connection refused"
            print('download Connect error')
            print(url)
            time.sleep(1)
            # return None
        except RequestException:  # 父类错误
            print('download Error')
            print(url)
            return None


# 歌曲专辑,图片信息
def writeDetails(id):
    url = 'https://music.163.com/song?id=%s' % id
    while True:
        try:
            response = session.get(url=url,headers=headers,timeout=3)
            soup = BeautifulSoup(response.text,"html5lib")
            img = soup.select("img.j-img")[0]['src']
            album = soup.select("head > meta:nth-child(32)")[0]['content']
            songDdetails['img'] = img
            songDdetails['album'] = album
            print(singerClassify)
            print(songDdetails)
            # insert_db()
            break
        except ReadTimeout:  # 访问超时的错误
            print('writeDetails Timeout')
            print(url)
            time.sleep(1)
            # return None
        except ConnectionError:  # 网络中断连接错误
            requests.status_code = "Connection refused"
            print('writeDetails Connect error')
            print(url)
            time.sleep(1)
            # return None
        except RequestException:  # 父类错误
            print('writeDetails Error')
            print(url)
            return None

# 存入数据库歌曲信息
def insert_db():
    # client = pymongo.MongoClient(MONGODB_URL)
    # db = client[MONGODB_DB]
    # table = db[MONGODB_TABLE]
    # 数据再次插入的时候避免重复
    # table.update({'_id': songDdetails['_id']}, {'$set': songDdetails}, True)
    # result = table.insert_one(songDdetails)
    effect_row = cur.execute(
        'INSERT IGNORE INTO `song_details`( `download_url`,`singer_id`,`singer`,`songName`,`album`,`img`) VALUES (%(downloadURL)s,%(singId)s, %(singer)s ,%(songName)s,%(album)s,%(img)s)',
        songDdetails)
    if effect_row:
        # 这一步才是真正的提交数据
        conn.commit()
    cur.close()
    conn.close()

# 存入歌手分类与歌手信息
def insert_mysql():
    # 字典的插入方式
    effect_row = cur.execute(
        'INSERT IGNORE INTO `singerInformation`( `singClassify`,`singClassifyId`,`singer`,`singId`) VALUES (%(singClassify)s,%(singClassifyId)s, %(singer)s ,%(singId)s)',
        singerInformation)
    if effect_row:
        # 这一步才是真正的提交数据
        conn.commit()
    effect = cur.execute(
        'INSERT IGNORE INTO `songsClassifiedNames`( `singClassifyId`,`singClassify`) VALUES (%s,%s)',
        (singerInformation['singClassifyId'], singerInformation['singClassify']))
    if effect:
        conn.commit()
    cur.close()
    conn.close()


if __name__=='__main__':
    # 根据榜单抓取
    # rankingList()
    # 根据歌手抓取
    singClassifyList()
    # 我的喜欢歌曲列表
    # songMessage