sycuricon( 八 ): benchmark
=======================================

为了对处理器的性能、正确性等进行验证，我们在 buildroot 平台移植了一些简单的 benchmark，后续应该会继续完善。
这部分代码和机制被我们继承在 riscv-rss-sdk 仓库当中，其他细节可以参看 riscv-rss-sdk 的介绍。

Lmbench
~~~~~~~~~~~~~~~~~~~~~~~~~~

简单介绍
--------------------------

Lmbench 的 submodule 定义如下，同步该仓库开始后续操作。正常的编译测试方式如下：

* 执行 make build，Lmbench 会执行 src 下的 make build，将 src 下的所有 c 文件编译为 elf 文件保存到 bin 目录下
* 执行 make results/make rerun，Lmbench 会执行 scripts 下面的 config-run 脚本，对 bin 的程序进行执行，并且保存执行结果

config-run 的执行方式是执行 benchmp 对需要测试的函数进行多线程的验证，然后每个线程跑一个测试函数。
该测试函数会对一个测试目标执行若干次，然后统计执行时间，进而计算平均执行时间。
例如执行 2^32 次 kill 操作计算 signal 传递操作的时间等。

.. remotecode:: ../_static/tmp/benchmark_link
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/0f62b52a0499830c76ff7562d323f76b69446afe/.gitmodules
	:language: text
	:type: github-permalink
	:lines: 25-27
	:caption: Lmbench 子模块定义

config-run 在执行程序的时候会先检查一下处理器的内存大小，如果内存大小满足测试需求，他才会开始进行测试。
这个内存检查过程非常慢，考虑到我们处理器内存一般是完全够用的，我们可以将对应的内存检查代码注释掉，节约内存检查的时间。

.. remotecode:: ../_static/tmp/lmbench_mem_config
	:url: https://github.com/docularxu/lmbench-3.0-a9/blob/37390e8321ce27b69642d3ac10b4dad46acb8ba4/scripts/config-run
	:language: text
	:type: github-permalink
	:lines: 200-223
	:caption: Lmbench 内存检查代码

移植过程
-------------------------------

现在我们需要将 benchmark 进行 riscv 交叉编译，因此需要修改 Lmbench 的一些配置。

修改编译依赖的 config 选项：

* 在 scripts/compiler 中设置 CC 为对应的交叉编译器路径 riscv64-unknown-linux-gnu-gcc

.. remotecode:: ../_static/tmp/lmbench_patch
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/0f62b52a0499830c76ff7562d323f76b69446afe/benchmark/patch/LmBench.patch
	:language: text
	:type: github-permalink
	:lines: 22-23
	:caption: Lmbench 编译器设置

* 在 scripts/OS 中设置 OS 为对应的 linux 类型 riscv-OS。之后编译的结果会出现在 bin/riscv-OS 中（不然默认是宿主机的 x86_64）

.. remotecode:: ../_static/tmp/lmbench_patch
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/0f62b52a0499830c76ff7562d323f76b69446afe/benchmark/patch/LmBench.patch
	:language: text
	:type: github-permalink
	:lines: 105-106
	:caption: Lmbench OS 环境设置

之后想要执行对应的测试，我们执行程序的环境需要 libtirpc，因此我们需要为交叉编译环境和执行环境配置 libtirpc 库。
我们可以回忆一下，我们的交叉编译链接库被保存在 toolchain/lib 中，因此我们需要在这里安装交叉编译的 libtirpc。

* 安装 libtirpc 库，这个可以从对应的官网直接下载解压到 benchmark 中，并且命名为 libtirpc
* 然后用 riscv 工具链交叉编译，然后 install 到 toolchian/lib 中

之后我们的交叉编译器就有了链接 libtirpc 的能力。
链接分为动态链接和静态链接，静态连接的程序拥有所有的代码，但是非常庞臃肿；
动态链接不需要链接对应的库代码，尺寸小巧，但是要求执行环境有对应的链接库。
因为我们的环境需要通过 SD 卡将程序读如内存进行执行，这个过程很慢，所以我们希望程序尽可能的小巧，因此我们采用动态链接编译。
然后我们需要额外的执行 install，将 libtirpc 保存到 sysroot 的 lib 目录下。
我们在 makefile 中编写了如下的代码，可以一键执行安装。

.. remotecode:: ../_static/tmp/benchmark_makefile
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/0f62b52a0499830c76ff7562d323f76b69446afe/Makefile
	:language: text
	:type: github-permalink
	:lines: 68-70
	:caption: tirpc 变量定义

.. remotecode:: ../_static/tmp/benchmark_makefile
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/0f62b52a0499830c76ff7562d323f76b69446afe/Makefile
	:language: text
	:type: github-permalink
	:lines: 226-233
	:caption: tirpc 编译安装

* 在 scripts/build 中修改编译选项 LDLIBS，加入 tirpc 和 pthread 的链接

.. remotecode:: ../_static/tmp/lmbench_patch
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/0f62b52a0499830c76ff7562d323f76b69446afe/benchmark/patch/LmBench.patch
	:language: text
	:type: github-permalink
	:lines: 9-10
	:caption: Lmbench 链接选项配置

* 在 Makefile 中修改编译选项 COMPILE，加入对 tirpc 的头文件 include 支持

.. remotecode:: ../_static/tmp/lmbench_patch
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/0f62b52a0499830c76ff7562d323f76b69446afe/benchmark/patch/LmBench.patch
	:language: text
	:type: github-permalink
	:lines: 115-116
	:caption: Lmbench 编译选项配置

之后执行编译就可以得到最后的结果。但是我们不方便把所有的 elf 和执行的 script 拷贝到我们的嵌入式环境 starship 中进行执行，
首先我们不需要执行所有的测试程序（太多了）；其次，我们很多测试程序的移植需要做调整，比较麻烦。
因此，我们额外写了一个 C 程序 execute.c 用 system 操作执行对应的测试程序，然后计算测试结果。
每个测试程序的执行命令被记录在 scripts/lmbench 当中，我们可以解析这个文件，
让 execute 程序执行需要测试的测试目标在 lmbench 中对应的执行命令。
在 Makefile 中加入对 execute 的编译命令即可。

.. remotecode:: ../_static/tmp/lmbench_patch
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/0f62b52a0499830c76ff7562d323f76b69446afe/benchmark/patch/LmBench.patch
	:language: text
	:type: github-permalink
	:lines: 120-133
	:caption: 加入 execute 编译

上述所有的修改，被我们打包到 benchmark/patch/lmbench.patch 当中，可以用 git apply 一键修改。

Unixbench
~~~~~~~~~~~~~~~~~~~~~~~~~~~

现在我们移植 unixbench，比 lmbench 简单一些。

简单介绍
--------------------------

* 执行 make program 可以编译 src 的所有程序，然后保存在 pgms 当中
* 执行 make run 可以 Run 脚本，这个脚本会依次执行 pgms 中的程序，然后将对应的执行结果和输出 log 保存在 result 中

和 lmbench 不同的是，unixbench 统计的不是每个测试的执行时间，而是执行时间的倒数。
unixbench 每个 elf 接受一个额外参数：执行时间 latency，然后这个 elf 会执行两个 thread。
主 thread 做 sleep 操作，sleep latency 的时间长度；另一个 thread 会执行测试函数，每执行一次给一个全局变量 +1。
当主 thread 从 sleep 醒来就会输出对应的副 thread 执行轮数作为执行分数，也就是单位时间内测试程序执行的次数，
也就是测试程序执行时间的倒数。这个分数越高说明执行越快，性能越好。

.. remotecode:: ../_static/tmp/benchmark_link
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/0f62b52a0499830c76ff7562d323f76b69446afe/.gitmodules
	:language: text
	:type: github-permalink
	:lines: 22-24
	:caption: Unixbench 子模块定义

移植过程
-------------------------------

修改编译依赖的 config 选项：

* 在 Makefile 中设置 CC 为对应的交叉编译器路径 riscv64-unknown-linux-gnu-gcc

.. remotecode:: ../_static/tmp/unxibench_patch
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/0f62b52a0499830c76ff7562d323f76b69446afe/benchmark/patch/UnixBench.patch
	:language: text
	:type: github-permalink
	:lines: 9-10
	:caption: Unxibench 编译器设置

* 在 Makefile 中设置 ARCH 为对应的 linux 类型 riscv64

.. remotecode:: ../_static/tmp/unxibench_patch
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/0f62b52a0499830c76ff7562d323f76b69446afe/benchmark/patch/UnixBench.patch
	:language: text
	:type: github-permalink
	:lines: 18-19
	:caption: Unixbench OS 环境设置

之后我们编写一个类似的 execute 程序来执行我们想测试的程序。

.. remotecode:: ../_static/tmp/unxibench_patch
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/0f62b52a0499830c76ff7562d323f76b69446afe/benchmark/patch/UnixBench.patch
	:language: text
	:type: github-permalink
	:lines: 20-48
	:caption: 加入 execute

上述所有的修改，被我们打包到 benchmark/patch/unixbench.patch 当中，可以用 git apply 一键修改。

文件系统调整
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

执行 benchmark_patch，将 benchmark/patch 的 lmbench.patch、unixbench.patch apply 到 Lmbench 和 Unixbench 中，完成上述的调整。

.. remotecode:: ../_static/tmp/benchmark_makefile
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/0f62b52a0499830c76ff7562d323f76b69446afe/Makefile
	:language: text
	:type: github-permalink
	:lines: 254-256
	:caption: benchmark 进行 patch

执行 benchmark，对 lmbench 和 unixbench 做编译，然后将编译的结果 Lmbench/bin/riscv-OS 和 Unixbench/pgms 拷贝到 sysroot 的 Lmbench 和 Unixbench 中。

.. remotecode:: ../_static/tmp/benchmark_makefile
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/0f62b52a0499830c76ff7562d323f76b69446afe/Makefile
	:language: text
	:type: github-permalink
	:lines: 250-252
	:caption: benchmark 安装

.. remotecode:: ../_static/tmp/benchmark_makefile
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/0f62b52a0499830c76ff7562d323f76b69446afe/Makefile
	:language: text
	:type: github-permalink
	:lines: 235-240
	:caption: lmbench 编译安装

.. remotecode:: ../_static/tmp/benchmark_makefile
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/0f62b52a0499830c76ff7562d323f76b69446afe/Makefile
	:language: text
	:type: github-permalink
	:lines: 218-224
	:caption: unixbench 编译安装

我们的一个测试程序需要对 /dev/zero、/dev/null 等进行操作，
所以需要我们的 buildroot 支持这些特殊设备，
所以我们需要对 conf/buildroot_initramfs_config 进行修改，加入 BR2_ROOTFS_DEVICE_CREATION_DYNAMIC_MDEV=y 的配置。

然后我们就可以重新构造镜像下板子了。

regvault 简单测试
~~~~~~~~~~~~~~~~~~~~~~~~~~~

前面的文章我们讲了添加 regvault 的硬件，然后我们需要执行对应的 regvault 指令测试的对应的正确性。
当然我们可以 linux 内核里面大规模的做插桩，然后直接运行，如果 linux 可以顺利启动，那么 regvault 的硬件实现就成功了。
但是如果执行失败了我们想要调试也是很困难的，所以我们应该先执行一个比较小的 regvault 测试程序做初步的测试。
所以我们设计了一个执行 regvault 的内核模块。

.. remotecode:: ../_static/tmp/regvault_kernel_module
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/27984ff9c70bdc2ef81b4274f1231278113597fa/benchmark/regvault/rgvlt_test.c
	:language: C
	:type: github-permalink
	:lines: 27-84
	:caption: regvault 内核测试模块

然后是对应的 makefile 文件，需要注意的是，因为需要链接的符号表、代码信息都是 build/linux 中交叉编译的结果，所以 KERNEL_DIR 是 build/linux 的结果。

.. remotecode:: ../_static/tmp/regvault_kernel_module_makefile
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/27984ff9c70bdc2ef81b4274f1231278113597fa/benchmark/regvault/Makefile
	:language: text
	:type: github-permalink
	:lines: 1-14
	:caption: regvault 内核测试模块的 Makefile

之后我们编译得到 rgvlt_test.ko，将他保存在文件系统的 regvault 文件夹中。

软件测试
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

上述程序的正确性可以在 spike 上进行验证。
我们先构造 spike 的镜像，然后在 spike 上执行这些程序验证。

* 进入 /Lmbench，然后执行 ./execute，就可以开始测试，测试结果如下：

.. code-block:: text     

    # cd /LmBench/
    # ./execute
    execute read
    pass 0
    Simple read: 8.5936 microseconds
    Elapsed time: 0.647 seconds
    execute write
    pass 0
    Simple write: 6.8206 microseconds
    Elapsed time: 0.647 seconds
    execute open
    pass 0
    Simple open/close: 192.6923 microseconds
    Elapsed time: 0.679 seconds
    execute select
    pass 0
    Select on 500 fd's: 774.1429 microseconds
    Elapsed time: 0.658 seconds
    ...

* 进入 /Unixbench，然后执行 ./execute，就可以开始测试，测试结果如下：

.. code-block:: text     

    # cd /UnixBench/
    # ./execute
    execute dhrystone
    pass 0
    COUNT|3665097|1|lps
    pass 1
    COUNT|3671664|1|lps
    pass 2
    COUNT|3672307|1|lps
    pass 3
    COUNT|3675095|1|lps
    pass 4
    COUNT|3676492|1|lps
    pass 5
    COUNT|3676371|1|lps
    pass 6
    COUNT|3675313|1|lps
    pass 7
    COUNT|3673990|1|lps
    Elapsed time: 80.639 seconds
    execute whetstone
    pass 0
    Calibrate
        0.11 Seconds          1   Passes (x 100)
        0.52 Seconds          5   Passes (x 100)
    ...

* 最后我们进入 /regvault，然后执行 insmod 操作进行验证；不过需要 spike 支持 regvault。

如果三个执行结果都没有问题，那么就说明软件应该没有明显问题，我们可以下板子进行性能测试了。

下板测试
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

下板之后的测试方式和 spike 上的测试方式是一样的。

测试结果使用串口输出，打印到机器的 screen 上面，然后可以用如下方式截取：

* ctrl+A+[：进入浏览模式，可以滚动滚轮上下拉动屏幕
* 空格：选择要复制的起点
* 滚轮：滚轮方向的内容都会被复制选中
* 空格：选择要复制的终点，这些部分会被保存到 copy buffer 中
* ctrl+A+>：将选择的内容保存到 /tmp/screen-exchange 中
* 之后在本机器的 /tmp/screen-exchange 获得这部分数据即可

需要注意，screen 不会保存所有的串口输出，只有大概 1000 行左右，所以要及时拷贝需要的数据。
