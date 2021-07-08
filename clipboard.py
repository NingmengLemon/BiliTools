import win32clipboard as w    
import win32con  
import win32api

def getText():#读取剪切板  
    w.OpenClipboard()
    try:
        d = w.GetClipboardData(win32con.CF_TEXT)
    except:
        return ''
    else:
        w.CloseClipboard()  
        return d.decode('utf-8','ignore')
    
def setText(aString):#写入剪切板  
    w.OpenClipboard()  
    w.EmptyClipboard()  
    w.SetClipboardText(aString)  
    w.CloseClipboard() 
