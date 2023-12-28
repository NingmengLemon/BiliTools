import random
import time
from configuration import platform

ALWAYS = lambda: True

refresh_by_human_combo = 0
refresh_by_human_count = 0
refresh_by_human_time_last = 0

# (text, appear_condition)
tips_random = [
    # 正经的Tips (什么？才这么点吗？？)
    ("点这里是可以刷新 Tips 哒 ヾ(•ω•`)o", ALWAYS),
    ("在列表框中可以按住 Ctrl 进行点选", ALWAYS),
    ("在列表框中可以按住 Shift 进行区间选择", ALWAYS),
    ("启动时使用 -debug 可以显示调试信息", ALWAYS),
    ("欢迎来给这个项目点小星星☆ (疯狂暗示)", ALWAYS),
    ("当焦点在主窗口输入框上时 可以用 Ctrl+Tab 快速切换输入模式", ALWAYS),
    # neta什么的, 总之就是各种不正经
    ("此程序还不完善，使用前请做好被Bug雷普的心理准备", ALWAYS),
    ("欢迎使用基于 Bug 开发 的BiliTools", ALWAYS),
    ("Bug 是此程序的重要组成部分，请勿修复（误", ALWAYS),
    ("有一个程序员前来修 Bug", ALWAYS),
    ("我好不容易写好一次，你却崩溃得这么彻底", ALWAYS),
    ("（`Oω|", ALWAYS),
    ("啊哈哈哈哈，我滴程序完成辣！", ALWAYS),
    ("世界——！", ALWAYS),
    ("Damedane ~ dameyo ~", ALWAYS),
    ("不写注释一时爽，维护程序火葬场", ALWAYS),
    ("让我看看你的程序正不正常啊♂", ALWAYS),
    ("✝升天✝✝升天✝✝升天✝", ALWAYS), 
    ("✝In Hell We Live, Lament✝", ALWAYS),
    ("不要停下来啊 （指 Debug", ALWAYS),
    ("Verify Code: 0d00 0721（？）", ALWAYS),
    ("请各位顾客不要在酒吧点炒饭（恼）", ALWAYS),
    ("今日份TO-DO：去码头整点薯条", ALWAYS),
    ("手持两把锟斤拷 口中疾呼烫烫烫", ALWAYS),
    ("你说得对，但是这就是 Earth: Online ，喜欢吗？", ALWAYS),
    ("当你看到这条 Tip 时，你就在看这条 Tip", ALWAYS),
    # 不对劲的Tips (柚子厨能不能退群啊.jpg)
    ("Ciallo～(∠・ω< )⌒☆", ALWAYS),
    ("不可能不可能不可能不可能这一定是梦", ALWAYS),
    ("……这个生物是怎么回事啊，从刚才开始就好萌", ALWAYS),
    ("这个遥控器是……房间的起爆装置！", ALWAYS),
    ("我很生气，好气好气的", ALWAYS),
    ("面硬加咸蔬菜加倍蒜末和油多多 plz", ALWAYS),
    # 比较正经, 但全是私货
    ("对嘲讽无需慈悲之心。", ALWAYS), 
    ("你的生命不是为了飘散而绽放的。", ALWAYS), 
    ("来吧，乘风破浪，将世俗的眼光统统超越。", ALWAYS), 
    ("心中怀抱着存在，就这样逐渐融化进晚霞中。", ALWAYS), 
    ("向着那一日所梦之景，纵身飞翔。", ALWAYS), 
    ("我就是不要做人啦！！", ALWAYS), 
    ("如果明天也活着就好啦。", ALWAYS), 
    ("在各自的心底，一定会闪耀属于各自独一无二的光辉。", ALWAYS), 
    ("全人类都做自己喜欢的事，世界就会灭亡。", ALWAYS), 
    ("如果只用开心的事和无聊的事能够填饱肚子，就好啦。", ALWAYS), 
    ("即使讨厌做人，也还是不能停止。", ALWAYS), 
    ("不论什么事情，都是某样东西的错呢。", ALWAYS), 
    ("剥掉外皮大家都是一样的，各位。", ALWAYS), 
    ("放心，总会有办法的...", ALWAYS), 
    ("一定要活下去，直到某日绽放笑容。", ALWAYS),
    ("为了回应别人的期待而郁郁寡欢，多无趣啊。", ALWAYS),
    ("奔跑不停的少年啊，直到来世也别止步。", ALWAYS), 
    ("生命不过一瞬，歌声却留永恒。", ALWAYS), 
    ("我要亲眼见到黎明的曙光！", ALWAYS), 
    ("这颗心，如同抬头所见的天空般，流光璨璨。", ALWAYS), 
    ("当爱超越时间，我们将再次相见。", ALWAYS), 
    ("要是放弃了个性，就跟死去没两样。", ALWAYS), 
    ("继续前行，因为未来呀，就在那里等我。", ALWAYS), 
    ("真正的天空，广阔且无论到哪里都紧紧相连。", ALWAYS), 
    ("我不会顾忌任何，因为我早已下定决心。", ALWAYS), 
    ("若不跨越最深的黑暗，便无法迎来黎明。", ALWAYS), 
    ("考验会使爱更加深厚。", ALWAYS), 
    ("祝你们的旅途，充满了诅咒与幸福。", ALWAYS), 
    ("万丈曙光之下，我们走上这条路，践行命运，追逐希望。", ALWAYS), 
    ("向着崭新黎明，我们踏上这征途。", ALWAYS), 
    ("愿悲伤退散，望痛苦消逝。", ALWAYS), 
    ("捡起来的一切，都将成为你的价值。", ALWAYS), 
    ("我们所度过的每个平凡的日常，也许就是连续发生的奇迹。", ALWAYS), 
    ("勇士啊，光芒与你同在。", ALWAYS),
    ("劲发____落，气收____平", ALWAYS),
    ("虽然歌声无形...", ALWAYS),

    ("居然真的有人在 Linux 上跑这个程序吗？！", lambda: platform=='linux'),
    ]

tips_prioritized = [
    ('阿伟你又在刷 Tips 了哦，休息一下吧', lambda: refresh_by_human_combo==3),
    ('你是否有些太闲了（恼）', lambda: refresh_by_human_combo==20)
]

def get_tip(by_human=False):
    global refresh_by_human_combo
    global refresh_by_human_count
    global refresh_by_human_time_last
    if by_human:
        refresh_by_human_combo += 1
        refresh_by_human_count += 1
    else:
        refresh_by_human_combo = 0
    for text, condition in tips_prioritized:
        if condition():
            refresh_by_human_time_last = time.time()
            return text
    while True:
        text, condition = random.choice(tips_random)
        if condition():
            refresh_by_human_time_last = time.time()
            return text

about_info = '''BiliTools v.{version}
这是一个使用 Python 编写的 Bilibili 工具箱.
为什么是 Python 呢？因为作者太拉了 只会用 Python 写应用 🤣👉
一些功能需要 FFmpeg 或 FFplay 的支持.
Made by: @NingmengLemon (GitHub)
更多信息请参见 GitHub 页面
---------------------------
此程序仅供学习与交流，不能用于任何非法用途.
使用本程序是你个人的自愿行为，使用本程序所造成的一切风险和不良后果均与作者本人无关.
感谢使用 (☆-v-)'''

