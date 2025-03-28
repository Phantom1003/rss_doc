sycuricon( 三 ): starship 仿真
========================================

上一章我们讲述了如何用 starship 进行综合下板，本章节我们将介绍如何用 starship 进行处理器仿真和处理器验证。

处理器验证
~~~~~~~~~~~~~~~~~~~~~~~~~~

我们使用差分测试技术进行处理器的验证，这里我们介绍处理器验证需要用到的技术原理和组件

差分测试
-----------------------

starship 使用差分测试技术进行处理器功能的验证。差分测试的基本流程如下：

* 首先我们生成一个指令序列作为测试程序，然后将它转换为处理器和仿真器可以接受的文件格式
* 处理器执行测试程序，每执行完一条（rob 提交一条）则调用模拟器同步执行一条
* 将模拟器执行的结果和处理器执行的结果进行对比，如果存在差异，则发现了一个实现上的 bug
* 如果比对成果没有问题，则让处理器继续执行直到执行完下一条，然后继续比较结果，不断循环

.. code-block:: text

                                +---------------+
                                |               |
                        +------>|   processor   |-----------+
                        |       |               |           |         
    +------------+      |       +---------------+           |        Y-----> continue
    |            |      |                                  \|/       |
    |  testcase  |------+                                compare-----+
    |            |      |                                  /|\       |
    +------------+      |       +---------------+           |        N-----> find bug
                        |       |               |           |
                        +------>|   simulation  |-----------+
                                |               |
                                +---------------+

当然差分测试需要解决几个难点：

* 仿真器能正确模拟处理器的行为，一般选择公认的黄金模型，比如用 spike 作为 RISCV 处理器的黄金模型
* 模块之间的指令执行和比较需要同步，一般依赖于处理器的提交阶段或者 ROB
* 处理器存在自己专门的设计实现问题，比如 CSR 的实现、MMIO 的实现，需要给处理器留下自由实现的空间
* 当发现存在不一致的时候，这个 bug 可能是处理器导致的，也可能是模拟器导致，甚至二者都有 bug；好在只有当两者错的一样的时候，才会出现假阴性

处理器模糊测试
-----------------------------

差分测试是在给定一个测试程序的情况下进行测试的，为了可以对处理器进行更充分地测试，我们借鉴软件的模糊测试技术进行硬件的模糊测试。模糊测试大致分为如下的几个步骤：

* testcase generator 负责生成各种测试样例
* differential test 接收测试样例进行差分测试
* 如果差分测试发现新的 bug 就交给 bug analysis 进行分析、归类、PoC 的生成
* 处理器内部进行必要的插桩，插桩的结果交给 coverage feedback 模块分析
* coverage feedback 分析的结果会反馈给 testcase generator，辅助测试样例的变异

.. code-block:: text

    +----------------------+            +---------------------+             +----------------+
    |                      |            |                     |             |                |
    |  testcase generator  |----------->|  differential test  |------------>|  bug analysis  |
    |                      |            |                     |             |                |
    +----------------------+            +---------------------+             +----------------+
                |                                   |
               /|\                                 \|/
                |                                   |
                |                       +---------------------+
                |                       |                     |
                +-------guide-----------|  coverage feedback  |
                                        |                     |
                                        +---------------------+

starship 的仿真验证流程可以对和 morfuzz 的仓库代码配置处理器进行模糊测试。

* testcase generator 的部分用 `razzle`_ 实现
* differential test 的部分用 riscv-isa-cosim 子模块实现
* coverage feedback 部分在 rocket-chip 生成的时候自动插桩
* MagicMakerBlockbox 模块配合指令随机数的生成

.. _razzle: https://github.com/sycuricon/razzle.git

riscv-isa-cosim
-----------------------------

为了让 spike 可以被方便地应用于差分测试，我们在 riscv-isa-sim 的基础上编写了 riscv-isa-cosim（starship 的 repo/riscv-isa-sim 其实是 riscv-isa-cosim）。在模块最早发表于我们的论文 `morfuzz`_。

.. _morfuzz: https://www.usenix.org/system/files/sec23fall-prepub-7-xu-jinyan.pdf

我们来介绍 cosim 提供的一些用于与差分测试的接口。首先我们需要构造一个和待验证处理器有尽可能类似的硬件结构的模拟器，下面是一个示例。首先用 config_t 数据结构记录需要模拟的处理器配置，然后用 cosim_cj_t 构造对应的处理器模拟器。

config_t 的一些配置如下：

* verbose：是否输出调试信息，如果这个选项是 true 的话，同步指令的时候会输出同步信息
* isa：支持的指令集架构，不在这个范围的一律当作 illegal instruction
* boot_addr：pc 初始化时的启动地址
* elffiles：载入内存的 testcase，这里可以将多个 elf 根据 segment 的地址对应关系载入内存
* mem_layout：内存区域范围，elf 的内存载入和处理器的内存读写超出这个范围会导致异常
* mmio_layout：MMIO 内存区域范围

其他更多的细节，详见 https://github.com/sycuricon/riscv-isa-cosim/blob/master/cosim/cj.h

.. code-block:: C++

    cosim_cj_t* simulator=NULL;
    config_t cfg;

    cfg.verbose = true;
    cfg.isa = "rv64i";
    cfg.boot_addr = 0x0;
    cfg.elffiles = std::vector<std::string> {
        "testcase.elf",
    };
    cfg.mem_layout = std::vector<mem_cfg_t> {
        mem_cfg_t(0x0UL, 0x2000UL),
        mem_cfg_t(0x10000UL, 0x14000UL),
        mem_cfg_t(0x80000000UL, 0x80400000UL)
    };
    cfg.mmio_layout = std::vector<mmio_cfg_t> {
        mmio_cfg_t(0x10000000UL, 0x1000UL),
        mmio_cfg_t(0x10001000UL, 0x1000UL),
        mmio_cfg_t(0x10002000UL, 0x1000UL),
    };
    simulator = new cosim_cj_t(cfg);

cosim 为差分测试提供了一些 api，一部分用于差分测试结果的比较，一部分用于测试程序查看和设置模拟器的状态。

* ``void proc_reset(unsigned id)`` ：处理器复位，id 是处理器的序号
* ``bool mmio_load(reg_t addr, size_t len, uint8_t* bytes)`` ：读 MMIO 的值
* ``bool mmio_store(reg_t addr, size_t len, const uint8_t* bytes);`` ：写 MMIO 的值
* ``reg_t get_tohost()`` ：获得模拟器写入 to_host 的值（参见 riscv-spike-sdk 一文）
* ``void set_tohost(reg_t value)`` ：向模拟器的 from_host 写入值
* ``int cosim_commit_stage(int hartid, reg_t dut_pc, uint32_t dut_insn, bool check)`` ：进行控制流的同步比较。如果 check = 0，则模拟器无条件执行下一条指令，如果 check = 1，模拟器执行完下一条指令之后，会比较传入的 pc 和 insn 的值和模拟器得到的结果是否一致。如果不一致会报错。该函数在执行的时候，如果 verbose = true，则会输出模拟器的执行结果作为调试信息。
* ``int cosim_judge_stage(int hartid, int dut_waddr, reg_t dut_wdata, bool fc)`` ： 进行数据流的同步比较。首先要用 cosim_commit_stage 执行一条指令，然后比较输入的 waddr、wdata 修改的是不是正确的 regfile 的寄存器编号和返回值。
* ``void cosim_raise_trap(int hartid, reg_t cause)`` ：触发传入的 cause 所指定的异常，可以让模拟器同步产生处理器的中断异常

我们现在来介绍一些使用 cosim 进行差分测试的思路和策略：

* 当处理器一条指令执行完毕时，首先执行 ``cosim_commit_stage`` 比较控制流转移是否正确，然后执行 ``cosim_judge_stage`` 比较数据流执行是否正确。这样可以检验控制流指令、异常跳转、寄存器读写是否正确。
* 对于内存写的指令，因为内存的外部情况是非常复杂的，我们很难提供一个统一的内存模型来进行比对，所以内存写操作一般不做直接的检验。而是在内存写之后读该地址的内存，如果读出来的值和之前写入的预期值保持一致，则认为写操作正确。
* 对于 CSR 寄存器，因为 csr 的一些 bit 的实现是未定义的，所以这些值读出的结果也是未定义的。因此对于 csr 指令的读操作的值如果存在差异，模拟器会自动同步处理器的 csr 的值，并给出 warn；他将 csr 正确性检查的责任交给测试者。
* 对于 MMIO，因为 MMIO 寄存器读出来的值都是处理器平台自己定义的，所以对于读地址落在 MMIO 的读内存操作，模拟器同步处理器读出来的结果，外设的正确性交给测试者自己负责。
* 如果处理器触发了中断异常，因为模拟器没有这部分中断定义，所以不会主动触发异常，这个时候处理器需要自己调用 ``cosim_raise_trap`` 将这个中断触发状态同步模拟器
* 对于 custom 指令，我们在后续的文章中做出介绍

DPI-C
----------------------------

将 C/C++ 函数当作 Verilog function 调用的技术，该技术仅用于 verilog 仿真，并不能用于 verilog 电路综合。

当我们进行 verilog 仿真的时候，往往是先将 verilog 转化为 C++ 语言的模块，然后执行这个 C++ 代码。因为 DPI-C 定义 function 直接是 C++ 实现的，这样在转化的时候就可以直接用该函数取代 verilog function。

我们可以将硬件模块内部的线路拉出来作为 dpi-c function 的参数，也可以将 dpi-c function 的结果保存到寄存器中，然后传递给其他硬件模块等等。

模拟器的函数接口可以用 dpi-c function 转化为 verilog 的调用接口，之后就可以实现 verilog 实现的处理器和 C++ 实现的模拟器之间的数据传输了。

testbench
--------------------------------

差分测试的模块代码位于 asic/sim 目录下，文件组成如下：

.. code-block:: sh

    .
    ├── FPGASimTop.v                # 被测试的处理器模块
    ├── spike_difftest.boom.v       # boom core 专用的差分测试代码
    ├── spike_difftest.cva6.v       # cva6 core 专用的差分测试代码
    ├── spike_difftest.rocket.v     # rocket core 专用的差分测试代码
    ├── spike_difftest.cc           # 差分测试的模块
    ├── spike_difftest.v
    └── Testbench.v                 # 顶层的测试模块

顶层模块 Testbench
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

顶层 Testbench.v 的模块图如下图所示

.. code-block:: text

                                +---------------+       +--------+
                                |               |       |        |      
                        +------>|  testharness  |------>|        |      +-------------+     +-------------+
                        |       |               |       |        |      |  dump_wave  |     |   coverage  |      
    +------------+      |       +---------------+       |        |      +-------------+     +-------------+      
    |            |      |                               |        |                 
    |  testcase  |------+                               |        |      +-------------+     +-------------+
    |            |      |    +--------------------------+        |      | memory_load |     | tracer_count|   
    +------------+      |    |  +---------------+                |      +-------------+     +-------------+      
                        |    |  |               |                |            
                        +------>|     cosim     |       RTLfuzz  |      +-------------+     +-------------+      
                             |  |               |                |      |   host_swap |     | fuzz_manager|    
                             |  +---------------+                |      +-------------+     +-------------+      
                             +-----------------------------------+            /|\
                                            |   |                              |
                                            |   +--------> to_host-------------+     
                                            +------------> error

该模块首先会解析命令行操作作为模块功能的开关：

* max-cycles：允许执行的最大周期数，之后 tracer_count 寄存器会开始计数，如果计数时间超过 max-cycles 就会因为超时导致验证失败。这可以防止测试程序出现死循环，或者处理器存在状态机阻塞等情况。如果测试程序的时间开销过大，则需要对此进行修改。
* dump：是否 dump 波形，如果设置了这个参数的话就会用 dumpfiles、dumpvars、fsdbDumpfile、fsdbDumpvars 等函数 dump 波形
* dump-start：开始 dump 波形的时间，这样可以少 dump 一部分波形，提高后续调试的效率
* verbose：差分测试时是否允许输出一些额外的调试信息
* testcase：用于测试的测试样例路径，它对应的 hex 文件会初始化处理器的内存，elf 文件会初始化模拟器的内存
* fuzzing：是否进行差分测试
* jtag_rbb_enable：是否进行 jtag 调试

testbench 内部包含如下几个模块各司其职：

* coverage_monitor mon：用于记录处理器内部的处理器状态覆盖率，用以衡量处理器测试的完整度
* fuzzer_manager：用于初始化模糊测试的配置，为后续的测试做准备，当 fuzzing 参数定义时被使用
* CJ rtlfuzz：用于差分测试，它调用 cosim 的 api 检查处理器执行结果是否正确，并且返回模拟器内部的 to_host 值
* TestHarness testHarness：用于测试的处理器

差分测试模块 rtlfuzz
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

首先是差分测试的主体部分，位于 asic/sim/spike_difftest.v。

该模块首先对 cosim_cj_t 做初始化，实例化出模拟器，然后调用每个处理器结构相关的特殊代码进行后续的差分测试。最后调用 cosim_get_tohost 的 dip-c function 获得模拟器内部的 host 的值。

.. remotecode:: ../_static/tmp/spike_difftest
	:url: https://github.com/sycuricon/starship/blob/974e2e6af819f7755f5e7d251b427a554fa082f3/asic/sim/spike_difftest.v
	:language: verilog
	:type: github-permalink
	:lines: 1-60
	:caption: 差分测试 CJ 模块

我们以 rocket-chip core 的差分测试为例进行介绍，我们来看 rocket-chip 硬件实现相关的用于差分测试的代码。这里包括三个部分：

* commit stage：调用 cosim_commit 对控制流正确性做出判断
* judge stage：调用 cosim_judge 对数据流正确性做出判断，因为 rocket-chip 有两个整数写口、两个浮点数写口，所以要做四个判断
* interrtupt：调用 cosim_raise_trap 同步外部中断异常

因为每个处理器的模块名、线名、写口个数、写回方式等都存在较大的差异，所以这部分代码只能手动处理，毕竟每个子类都要做虚函数重载的。

.. remotecode:: ../_static/tmp/spike_difftest.rocket
	:url: https://github.com/sycuricon/starship/blob/974e2e6af819f7755f5e7d251b427a554fa082f3/asic/sim/spike_difftest.rocket.v
	:language: verilog
	:type: github-permalink
	:caption: 差分测试模块的 rocket 架构相关代码

处理器仿真
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

处理器仿真我们提供了 verilator 和 VCS 两套工具链 flow，之后我们会依次介绍两者的脚本调用，在实际上用上其实大同小异。

前期准备
---------------------------------------

首先修改 conf/build.mk 对需要生成的处理器配置进行选择。

.. code-block:: Makefile

    # Verilog Generation Configuration
    ##################################

    STARSHIP_CORE   ?= Rocket
    STARSHIP_FREQ   ?= 100
    STARSHIP_TH     ?= starship.asic.TestHarness
    STARSHIP_TOP    ?= starship.asic.StarshipSimTop
    STARSHIP_CONFIG ?= starship.asic.StarshipSimConfig

对应的模块位于 repo/starship/src/main/scala/asic 当中。和 fpga 主要的区别在于：

* asic 没有 spi 外设接口，给 uart、memory 等外设接口提供了仿真的外设模块
* 加入了一个用于模糊测试的数据变异模块、随机数生成模块、coverage 插桩等

为了可以进行 fuzzing 还需要给 rocket-chip 模块代码应用补丁，进行硬件插桩。执行

.. code-block:: sh

    cd repo/rocket-chip
    git apply ../../patch/rocket-chip/*

rocket-chip 的各个补丁作用如下：

* 1.patch：在 IBuf 增加 MagicMakerBlockbox 模块，用于模糊测试
* 2.patch：增加硬件断点个数
* 3.patch：将提交 log 的打印使能
* 4.patch：增加 commit 测试、judge 测试时候的输出 log
* 5.patch：生成 MagicMaskerBlackbox 模块，用于模糊测试

之后执行 ``make verilog`` 生成 sim 对应的 testharness 代码。

之后还要执行 ``make verilog-patch`` 来对生成的 verilog 进行修改，主要使用一系列的 sed 进行字符串替换：

* 实际运行的时候处理器从 0x10000 启动，然后将程序从外部存储搬运到内存；但是仿真的时候，readmemh 函数可以直接将程序载入内存，因此直接从 0x8000000 开始启动就可以了。这里将 s2_pc 寄存器的初始值修改为 0x8000000，就实现了这个效果。
* 同理，将 core_boot_addr 等其他的起始地址从 0x10000 修改为 0x80000000
* 插桩的初始值从随机数修改为 0，在 fpga 的 flow 中这些部分是不需要的，随意可以随便赋值；但是现在需要 covsum 的结果做覆盖率，那么就需要初始化为 0。

.. remotecode:: ../_static/tmp/starship_makefile
	:url: https://github.com/sycuricon/starship/blob/974e2e6af819f7755f5e7d251b427a554fa082f3/Makefile
	:language: Makefile
	:type: github-permalink
	:lines: 138-146
	:caption: verilog 代码调整 

riscv-isa-cosim 库编译
------------------------------

为 Verilog 的差分测试模块可以调用 cosim 的 api，我们需要将 riscv-isa-cosim 编译为链接库。

.. remotecode:: ../_static/tmp/starship_makefile
	:url: https://github.com/sycuricon/starship/blob/974e2e6af819f7755f5e7d251b427a554fa082f3/Makefile
	:language: Makefile
	:type: github-permalink
	:lines: 194-199
	:caption: cosim 编译变量    

* repo/riscv-isa-sim：riscv-isa-cosim 的源代码
* build/spike：编译 cosim 的工作区，编译得到的链接库也在其中
* spike 链接库：编译得到的链接库位于 build/spike，包括

  * libcosim.a：用于 cosim 差分测试
  * libriscv.a：用于 riscv 指令解析和模拟
  * libdisasm.a：用于反汇编
  * libsoftfloat.a：用于软浮点运算
  * libfesvr.a：用于 spike 和 host 交互
  * libfdt.a：用于设备树解析

* spike 头文件：位于 cosim 源代码的各个路径和 build 的各个路径

.. remotecode:: ../_static/tmp/starship_makefile
	:url: https://github.com/sycuricon/starship/blob/974e2e6af819f7755f5e7d251b427a554fa082f3/Makefile
	:language: Makefile
	:type: github-permalink
	:lines: 201-208
	:caption: cosim 链接库编译

之后执行 ``$(SPIKE_LIB)&`` target，在 build/spike 执行 configure 和 make 即可。这个编译过程其实和 rss 的 spike 编译方式一样，只是没有 install 而已。

verilator 仿真
------------------------------

`verilator`_ 是开源的 verilog 模拟工具，它会将 verilog 先转化为 C++ 代码和驱动程序，然后通过执行 C++ 来进行 Veriog 仿真。支持 verilog、systemverilog 语法，支持仿真激励，支持 dpi-c。

.. _verilator: https://github.com/verilator/verilator.git

.. remotecode:: ../_static/tmp/starship_makefile
	:url: https://github.com/sycuricon/starship/blob/974e2e6af819f7755f5e7d251b427a554fa082f3/Makefile
	:language: Makefile
	:type: github-permalink
	:lines: 292-328
	:caption: verilator 仿真变量参数

verilator 涉及到一大堆的配置参数

* build/verilator：verilator 编译结果的工作区
* build/verilator/wave：verilator dump 波形的工作区
* build/verilator/Testbench：verilator 编译得到的用于模拟的可执行程序
* VLT_CFLAGS：verilator 将 verilog 转化为 C/C++ 之后，用于 gcc/g++ 编译的参数配置
* VLT_SRC_C：用于编译的 C 代码，用于 DPI-C，包括 build/spike 的 C 代码和 asic/sim 的 C 代码
* VLT_SRC_V：用于编译的 Verilog 代码，位于 asic/sim
* VLT_DEFINE：为 verilog 的编译传递宏定义，包括是否 define 和 define 的值
* VLT_OPTION：verilator 需要的执行参数，包括允许 dump 波形（--trace）、提供顶层激励（--main）、提供 C 编译选项（-CFLAGS）等
* VLT_SIM_OPTION：为 verilog 中的 plusargs 函数提供变量参数

除了 vlt target 用于最基本的编译执行，Makefile 还提供了三个额外的 target 对配置进行开关。

* vlt-wave：允许 dump 波形
* vlt-jtag：允许 jtag 调试
* vlt-jtag-debug：即允许 jtag 调试，又允许 dump 波形

.. remotecode:: ../_static/tmp/starship_makefile
	:url: https://github.com/sycuricon/starship/blob/974e2e6af819f7755f5e7d251b427a554fa082f3/Makefile
	:language: Makefile
	:type: github-permalink
	:lines: 330-344
	:caption: verilator 仿真

* $(VLT_TARGET) 依赖于 rocket-chip 生成的 verilog，依赖于 cosim 的静态链接库，依赖于 asic/sim 的测试代码
* 执行 ``$(VLT_TARGET)``，verilator 根据一些列配置将所有的 Verilog、Cpp 文件编译为最后的 Testbench
* 执行 ``make vlt`` 执行 Tetsbench 进行仿真；执行 vlt-wave、vlt-jtag、vlt-jtag-debug 可以启动额外的功能，dump 的波形位于 build/verilator/wave 文件夹下的 vcd 文件
* 执行 ``make gtkwave`` 可以用 gtkwave 工具打开 dump 的波形文件

测试程序传递
---------------------------------

测试程序地址记录在 conf/build.mk 中

.. remotecode:: ../_static/tmp/starship_conf_build_mk
	:url: https://github.com/sycuricon/starship/blob/974e2e6af819f7755f5e7d251b427a554fa082f3/conf/build.mk
	:language: Makefile
	:type: github-permalink
	:lines: 17-24
	:caption: 仿真测试程序设置

STARSHIP_TESTCASE 指示了测试样例的 elf 文件的绝对路径。默认的情况下这个文件是 starship-dummp-testcase，Makefile 会从 github 上下载这个文件，然后执行。

.. remotecode:: ../_static/tmp/starship_makefile
	:url: https://github.com/sycuricon/starship/blob/974e2e6af819f7755f5e7d251b427a554fa082f3/Makefile
	:language: Makefile
	:type: github-permalink
	:lines: 181-183
	:caption: 测试程序路径变量

.. remotecode:: ../_static/tmp/starship_makefile
	:url: https://github.com/sycuricon/starship/blob/974e2e6af819f7755f5e7d251b427a554fa082f3/Makefile
	:language: Makefile
	:type: github-permalink
	:lines: 265-272
	:caption: 测试程序 hex 文件生成

之后这个 elf 文件会被转化为对应的 hex 文件，然后通过 +testcase 参数把路径传递给模拟执行的 verilog。elf 文件被 cosim 链接库的模拟器加载，hex 被处理器加载，然后开始做差分测试。

VCS 仿真执行
------------------------------------

VCS 是工业级的仿真和综合软件，需要先安装 VCS 的正版软件并且购买证书才可以使用，如果是小作坊的话使用开源的 verilator 即可。

VCS 的参数配置和 verilator 保持对偶，所以就不一一介绍了，大家类比即可。

.. remotecode:: ../_static/tmp/starship_makefile
	:url: https://github.com/sycuricon/starship/blob/974e2e6af819f7755f5e7d251b427a554fa082f3/Makefile
	:language: Makefile
	:type: github-permalink
	:lines: 274-290
	:caption: vcs 仿真

* 执行 ``make vcs`` 即可 vcs 编译执行
* vcs-wave 可以额外 dump 波形
* vcs-debug 可以让模拟器输出指令执行时的调试信息
* vcs-fuzz 可以进行模糊测试
* vcs-fuzz-debug 可以在模糊测试的同时输出调试信息
* vcs-jtag 可以进行 jtag 调试
* vcs-jtag-debug 可以在 jtag 调试的同时输出指令执行的调试信息
* ``make verdi`` 用 verdi 工具打开 fsdb 波形文件，是非常好用的调试工具

至此 starship 仿真和测试的基本流程介绍完毕。

riscv-tests 的使用
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

处理器模糊测试需要特殊的软件支持和环境配置，执行的时间成本和技术成本比较高，往往用于复杂 bug 的挖掘和充分的验证。在多数情况下，使用现成的测试程序进行验证，就可以覆盖各种指令边界条件、特权级和地址模式。RISCV 官方提供了 riscv-tests 仓库提供丰富的测试样例，我们可以使用这些测试样例进行基本功能的覆盖测试，starship-dummy-testcase 就是用 riscv-tests 为基础设计产生的。

执行如下的指令序列就可以对 riscv-tests 进行下载、编译、测试样例的安装：

.. code-block:: sh

    git clone https://github.com/riscv/riscv-tests
    cd riscv-tests
    git submodule update --init --recursive
    autoconf
    ./configure --prefix=$RISCV/target
    make
    make install

riscv-tests 的比较重要的文件目录如下：

.. code-block:: sh

    .
    ├── benchmarks          # 一些大的性能测试，比较复杂的处理逻辑
    ├── env 
    |   ├── encoding.h      # 提供一些编码的宏
    |   ├── LICENSE 
    |   ├── p               # 提供一些物理地址模式相关的宏
    |   ├── pm              # 提供一些多核物理地址模式相关的宏
    |   ├── pt              # 提供一些时钟中断物理地址模式相关的宏
    |   └── v               # 提供一些虚拟地址模式相关的宏
    ├── isa                 # 一些指令功能测试
    ├── LICENSE             
    ├── Makefile        
    ├── mt                  # 一些矩阵向量测试
    └── README.md

对于 isa 的测试程序，它的功能可以通过命名窥见一斑。比如 ``rv64ua-v-amomin_w`` 是 rv64 处理器、a 指令扩展、虚拟地址执行模式、amomin_w 指令的测试程序。当使用 isa 的测试程序进行测试的时候首先要检查地址长度、指令集架构、地址模式是否支持，然后再开始测试。

我们以 rv64ui-p-add 测试为例来看一下 riscv-tests 的测试逻辑。根据 dump 我们可以看到对应的代码组织如下：

.. code-block:: text

    +-----------------------------------+
    |   _start:     j reset_vector      |
    +-----------------------------------+
    |                                   |
    |           trap_vector             |
    |                                   |
    +-----------------------------------+
    |   write_tohost: sw gp, tohost     |
    +-----------------------------------+
    |                                   |
    |           reset_vector            |
    |                                   |
    +-----------------------------------+
    |   test_2:     li gp, 2            |
    |               li a1, 0            |
    |               li a2, 0            |
    |               add a4, a1, a2      |
    |               li t2, 0            |
    |               bne a4, t2, fail    |
    +-----------------------------------+
    |           test_3                  |
    +-----------------------------------+
    |           test_4                  |
    +-----------------------------------+
    |           ......                  |
    +-----------------------------------+
    |           j pass                  |
    +-----------------------------------+
    |   fail:       fence               |
    |               slli gp, gp, 1      |
    |               ori gp, gp, 1       |
    |               ecall               |
    +-----------------------------------+
    |   pass:       fence               |
    |               li gp, 1            |
    |               ecall               |
    +-----------------------------------+

* 首先执行 _start 跳到 reset_vector
* reset_vector 开始做初始化，对所有通用寄存器赋初值，对 csr 赋值，mret 到对应的特权态和地址
* 执行后续的测试，每个测试的逻辑基本是，gp 设置为 test 编号，给寄存器赋值，执行待测指令，比较返回结果和预期的立即数是否保持一致，如果一致就继续执行下一个测试，不然跳到 fail
* 通过所有测试最后进入 pass 分支，将 gp 设置为 1，然后 ecall 进入 trap handler
* 没有通过测试进入 fail 分支，将 gp 设置为 ``(gp<<1)+1`` ，然后 ecall 进入 trap_handler
* trap_handler 进入 write_tohost，将 gp 的值写入 to_host 寄存器给 host
* host 检查结果是 1，则说明通过测试；结果不是 1，根据高位定位错误的 test 位置


