# T1Process

学习HCP pipeline的处理方式，目前基本就是完全扒了下来，有些地方舍弃掉了。
目前没有Include进T2序列

全部流程主要为：
1.梯度畸变矫正
2.去头皮
3.偏置场矫正
4.空间标准化

现在来看去头皮效果一般，不过速度还不错。全部下来一个人的预处理时间在20min左右。
可以选择用recon-all来去头皮，预计时间会再增加12min（TODO）。

![去头皮效果图](https://github.com/podismine/T1Process/blob/master/1601025307(1).png)
