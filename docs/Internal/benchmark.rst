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
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/0f62b52a0499830c76ff7562d323f76b69446afe/.gitmodules
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
让 execute 程序执行需要测试的测试目标在 lmbench 中对应的执行命令。在 Makefile 中加入对 execute 的编译命令即可。

.. remotecode:: ../_static/tmp/lmbench_patch
	:url: https://github.com/sycuricon/riscv-spike-sdk/blob/0f62b52a0499830c76ff7562d323f76b69446afe/benchmark/patch/LmBench.patch
	:language: text
	:type: github-permalink
	:lines: 120-133
	:caption: 加入 execute 编译

Unixbench
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. remotecode:: ../_static/tmp/benchmark_link
	:url: https://github.com/Phantom1003/rocket-chip/blob/53d8185a0e5cc1258acaccb60a89bfd60cbc58a1/src/main/scala/scie/SCIE.scala
	:language: text
	:type: github-permalink
	:lines: 22-24
	:caption: Unixbench 子模块定义



