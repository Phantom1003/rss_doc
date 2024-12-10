sycuricon( 六 ): 流片
======================================

我们在 rocket-chip 的 regvault 扩展的基础上进行整改，然后将该设计用于芯片流片。

流片起因：浙大求是安全芯 ZJV
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

浙大求是安全芯是浙江大学网安学院系统所常瑞老师、申文博老师的芯片项目，旨在实现芯片安全架构扩展和提供真实的芯片实验平台。

求是安全芯 I 号实现了 rocket-chip 的 regvault 扩展，我们小组负责处理器内核的前端设计，由香山实验室方面提供处理器外围和后端版图，最后交给代工厂流片。

前端代码调整和实现
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

为了让我们 rocket-chip 的核内实现和香山实验室提供的芯片外围可以对接起来，我们需要对 rocket-chip 做一些调整，我们在 regvault 的基础上新建了 no-io 分支来实现这部分内容。

删除处理器外围
---------------------------------

因为我们的处理器使用香山的外围，所以我们需要首先删除 VC707Shell 提供的外围和其他的外设支持。我们在 repo/starship/src/main/scala 中新建了 Axi4 文件夹，里面是对应的模块实现，旨在删除外围部件，仅保留一个 memory 接口和一个 MMIO 接口。

修改 AXI4Top.scala 模块：

* 定义 StarshipAxi4Top 作为顶层模块
* 定义 StarshipAxi4TopModuleImp 作为顶层模块的实现
* 将原有的 PeripherySPIKey、PeripheryUARTKey 等配置删除，不生成 SPI、UART 等外设驱动
* 仅保留 CanHaveMasterAXI4MemPort、CanHaveMasterAXI4MMIOPort、HasPeripheryDebug，保留内存总线接口、MMIO 接口、调试模块接口

.. remotecode:: ../_static/tmp/starship_axi4_top
	:url: https://github.com/sycuricon/starship/blob/fd5d82309900869f8787f1141857f770a499b738/repo/starship/src/main/scala/axi4/AXI4Top.scala
	:language: scala
	:type: github-permalink
	:lines: 18-33
	:caption: StarshipAxi4Top

删除处理器插桩
----------------------

因为我们之前的处理器用于模糊测试，所以需要在处理器生成的过程中进行插桩，因此我们在 repo/starship/src/main/scala/utils/StarshipStage.scala 中定义了插桩的过程。

我们将 override 的 run 函数进行修改，将里面的 ``RunFirrtlTransformAnnotation(Dependency[CoverageInstrument])`` 注释掉，这样生成的 verilog 就没有对应的 coverage_sum 的插桩了。

.. remotecode:: ../_static/tmp/starship_axi4_stage
	:url: https://github.com/sycuricon/starship/blob/fd5d82309900869f8787f1141857f770a499b738/repo/starship/src/main/scala/utils/StarshipStage.scala
	:language: scala
	:type: github-permalink
	:lines: 106-114
	:caption: 删除 coverage sum 插桩

修改 MMIO 范围
--------------------------

香山提供的外围的 MMIO 地址范围在 0x1000000-0x80000000，所以我们需要将 MMIO 的地址范围做对应的修改，不然到时候核内寻址不会将地址读写请求从 MMIO 口中发送出来。

这里对 Config.scala 进行修改，可以看到 BaseConfig 对 ExtBus 参数进行了修改，将 base 设置为 0x1000_0000，将 size 设置为 0x7000_0000。

.. remotecode:: ../_static/tmp/starship_axi4_base_config
	:url: https://github.com/sycuricon/starship/blob/fd5d82309900869f8787f1141857f770a499b738/repo/starship/src/main/scala/Configs.scala
	:language: scala
	:type: github-permalink
	:lines: 40-66
	:caption: 修改 ExtBus 范围

这样我们就完成了对 MMIO 范围的修改，此时我们生成最后的 verilog，可以检查对应的设备树，可以看到：

.. code-block:: text

    L12: mmio-port-axi4@10000000 {
        #address-cells = <1>;
        #size-cells = <1>;
        compatible = "simple-bus";
        ranges = <0x10000000 0x10000000 0x70000000>;
    };

启动过程调整
-----------------------

在香山提供的启动过程中，我们的处理器从 0x30000000 开始启动，然后开始访问对应地址范围的 flash。该 flash 前半部分是一段启动代码，后半部分是系统程序镜像，处理器执行前半部分的启动代码将程序镜像 copy 到内存中，然后开始后续的系统启动。

所以我们让处理器在 zsbl 当中执行 0x30000000 的跳转。所以对 firmware 的 zsbl 代码进行调整，修改为

.. remotecode:: ../_static/tmp/starship_axi4_zsbl
	:url: https://github.com/sycuricon/starship/blob/fd5d82309900869f8787f1141857f770a499b738/firmware/zsbl/bootrom.S
	:language: scala
	:type: github-permalink
	:caption: zsbl 跳转到 0x30000000 启动

这一看到这个时候 maskrom 已经没有用了，所以我们可以把 maskrom 删除掉。修改 Top.scala 的 StarshipSystem，删除 maskrom 的实例化：

.. remotecode:: ../_static/tmp/starship_axi4_base_top
	:url: https://github.com/sycuricon/starship/blob/fd5d82309900869f8787f1141857f770a499b738/repo/starship/src/main/scala/Top.scala
	:language: scala
	:type: github-permalink
	:lines: 19-24
	:caption: 删除 maskrom

在 AXI4Top/Config.scala，在原来 regvault 的 Config 的基础上，删除了 WithPeripherals 配置，这样内部的 TileLink 就不会生成 maskrom 对应的路由。

.. remotecode:: ../_static/tmp/starship_axi4_config
	:url: https://github.com/sycuricon/starship/blob/fd5d82309900869f8787f1141857f770a499b738/repo/starship/src/main/scala/axi4/Configs.scala
	:language: scala
	:type: github-permalink
	:lines: 15-30
	:caption: 删除 WithPeripherals

Verilog 代码生成
----------------------------

修改 conf/build.mk 的配置为对应的：

.. remotecode:: ../_static/tmp/starship_axi4_conf_build_mk
	:url: https://github.com/sycuricon/starship/blob/fd5d82309900869f8787f1141857f770a499b738/conf/build.mk
	:language: scala
	:type: github-permalink
	:lines: 1-8
	:caption: axi4 对应的生成配置

然后执行 ``make vlt`` 就可以得到需要的代码，我们将必要的代码取出即可：

* plusarg_reader.v
* Rocket.StarshipAxi4Top.StarshipAxi4DebugConfig.top.v

IP 核的替换
-------------------

我们 Top 内部的 cache 是用 array 实现的，但是当我们将代码综合为后端版图的时候，这些 array 只能被综合成一些离散的寄存器。但实际上为了节约芯片面积，我们希望用 sram IP 核来替换这些 array 模块，这样我们综合的版图就可以用 SRAM 实现 cache。

需要替换的主要就是 icache、dcache 的 data array 和 tage array，他们的尺寸可以用 512x64、64x84、64x88 的 sram ip 拼接而成。我们用 sram 自动化工具生成对应的 sram 文件，其中一个的模块声明如下：

.. code-block:: verilog

    module TS5N28HPCPLVTA64X84M2FW (
        CLK, CEB, WEB,
        A, D,
        BWEB,
        Q);
    
    //=== IO Ports ===//

    // Normal Mode Input
    input CLK;
    input CEB;
    input WEB;
    input [5:0] A;
    input [83:0] D;
    input [83:0] BWEB;

    // Data Output
    output [83:0] Q;

* CEB：芯片使能信号，只有当 CEB=0 的时候才可以执行读写操作
* WEB：芯片写使能信号，只有当 WEB=0 的时候才可以执行写操作
* A：地址信号线
* D：数据信号线
* BWEB：芯片位写使能信号线，只有当对应位的 BWEB=0 的时候才可以对这个位执行写操作
* Q：芯片数据输出
* 时序：芯片的读写操作都需要等待一个周期完成

然后我们对 Top 中的 array 进行替换，实际上只需要对自动化生成的 array 模块做替换即可，但是因为经验不足对 top 的源代码做了替换，到之后后续每次重新生成 top 都要替换一次代码。

.. code-block:: Verilog

    module tag_array_0(
        input  [5:0]  RW0_addr,
        input         RW0_en,
        input         RW0_clk,
        input         RW0_wmode,
        input  [20:0] RW0_wdata_0,
        input  [20:0] RW0_wdata_1,
        input  [20:0] RW0_wdata_2,
        input  [20:0] RW0_wdata_3,
        output [20:0] RW0_rdata_0,
        output [20:0] RW0_rdata_1,
        output [20:0] RW0_rdata_2,
        output [20:0] RW0_rdata_3,
        input         RW0_wmask_0,
        input         RW0_wmask_1,
        input         RW0_wmask_2,
        input         RW0_wmask_3
    );
        wire [5:0] tag_array_0_ext_RW0_addr;
        wire  tag_array_0_ext_RW0_en;
        wire  tag_array_0_ext_RW0_clk;
        wire  tag_array_0_ext_RW0_wmode;
        wire [83:0] tag_array_0_ext_RW0_wdata;
        wire [83:0] tag_array_0_ext_RW0_rdata;
        wire [3:0] tag_array_0_ext_RW0_wmask;
        wire [41:0] _GEN_0 = {RW0_wdata_3,RW0_wdata_2};
        wire [41:0] _GEN_1 = {RW0_wdata_1,RW0_wdata_0};
        wire [1:0] _GEN_2 = {RW0_wmask_3,RW0_wmask_2};
        wire [1:0] _GEN_3 = {RW0_wmask_1,RW0_wmask_0};

        wire [83:0] sram_wmask;
        genvar i;
        generate
            for(i=0;i<=3;i=i+1)begin:tag_array_0
            assign sram_wmask[i*21+20:i*21]={21{~tag_array_0_ext_RW0_wmask[i]}};
            end
        endgenerate

        TS5N28HPCPLVTA64X84M2FW tag_array_0_ext (
            .A(tag_array_0_ext_RW0_addr),
            .CEB(~tag_array_0_ext_RW0_en),
            .CLK(tag_array_0_ext_RW0_clk),
            .WEB(~tag_array_0_ext_RW0_wmode),
            .D(tag_array_0_ext_RW0_wdata),
            .Q(tag_array_0_ext_RW0_rdata),
            .BWEB(sram_wmask)
        );

        assign tag_array_0_ext_RW0_clk = RW0_clk;
        assign tag_array_0_ext_RW0_en = RW0_en;
        assign tag_array_0_ext_RW0_addr = RW0_addr;
        assign RW0_rdata_0 = tag_array_0_ext_RW0_rdata[20:0];
        assign RW0_rdata_1 = tag_array_0_ext_RW0_rdata[41:21];
        assign RW0_rdata_2 = tag_array_0_ext_RW0_rdata[62:42];
        assign RW0_rdata_3 = tag_array_0_ext_RW0_rdata[83:63];
        assign tag_array_0_ext_RW0_wmode = RW0_wmode;
        assign tag_array_0_ext_RW0_wdata = {_GEN_0,_GEN_1};
        assign tag_array_0_ext_RW0_wmask = {_GEN_2,_GEN_3};
    endmodule

注意：

* rocket 中的使能信号都是高电平使能，这里需要手动修改为低电平使能
* rocket 的段使能都是多位的，而 sram 的段使能是单位的，需要做一个转换

接入香山外围
-----------------------

这部分由香山实验室提供测试仿真的外围环境，因为他们的外围只有一个面向处理器的 AXI 口，因此需要额外生成一个 NIC 桥将我们处理器的两个口转换为一个口，然后和外围连接。

这部分代码因为是对方机密，所以不予开源。

增加 debug module 支持
--------------------------

我们将 Testharness 当中 Top 外围的 debug module 的连接模块从源文件中剥离出来，然后让 Top 进行连接，这部分的电路图我们在 debug module 一文中已经绘制过了，现在将 debug module 相关的代码附加如下，需要的朋友可以自己 copy：

.. code-block:: Verilog

    module core_wrapper (
        input  logic        clock,
        input  logic        reset,
        input  logic        io_debug_reset,
        input  logic        io_jtag_TCK,
        input  logic        io_jtag_TMS,
        input  logic        io_jtag_TDI,
        output logic        io_jtag_TDO,
        ...
    );

    logic top_clock;
    logic top_reset;
    logic top_resetctrl_hartIsInReset_0;
    logic debug_clock;
    logic debug_reset;
    logic debug_systemjtag_reset;
    logic debug_ndreset;
    logic debug_dmactive;
    logic debug_dmactiveAck;

    TopJTAGLInk u_TopJTAGLInk (
        .clock                        (clock),
        .io_reset                     (reset),
        .io_debug_reset               (io_debug_reset),
        .top_clock                    (top_clock),
        .top_reset                    (top_reset),
        .top_resetctrl_hartIsInReset_0(top_resetctrl_hartIsInReset_0),
        .debug_clock                  (debug_clock),
        .debug_reset                  (debug_reset),
        .debug_systemjtag_reset       (debug_systemjtag_reset),
        .debug_ndreset                (debug_ndreset),
        .debug_dmactive               (debug_dmactive),
        .debug_dmactiveAck            (debug_dmactiveAck)
    );

    assign io_mst_mmio_araddr[31] = '0;
    assign io_mst_mmio_awaddr[31] = '0;
    StarshipAxi4Top u_StarshipAxi4Top (
        .clock                           (top_clock),
        .reset                           (top_reset),
        .resetctrl_hartIsInReset_0       (top_resetctrl_hartIsInReset_0),
        .debug_clock                     (debug_clock),
        .debug_reset                     (debug_reset),
        .debug_systemjtag_jtag_TCK       (io_jtag_TCK),
        .debug_systemjtag_jtag_TMS       (io_jtag_TMS),
        .debug_systemjtag_jtag_TDI       (io_jtag_TDI),
        .debug_systemjtag_jtag_TDO_data  (io_jtag_TDO),
        .debug_systemjtag_jtag_TDO_driven(),
        .debug_systemjtag_reset          (debug_systemjtag_reset),
        .debug_systemjtag_mfr_id         ('0),
        .debug_systemjtag_part_number    ('0),
        .debug_systemjtag_version        ('0),
        .debug_ndreset                   (debug_ndreset),
        .debug_dmactive                  (debug_dmactive),
        .debug_dmactiveAck               (debug_dmactiveAck),
        ...
    );

    endmodule

    module TopJTAGLInk (
        input logic clock,
        input logic io_reset,
        input logic io_debug_reset,

        output logic top_clock,
        output logic top_reset,
        output logic top_resetctrl_hartIsInReset_0,
        output logic debug_clock,
        output logic debug_reset,
        output logic debug_systemjtag_reset,
        input  logic debug_ndreset,
        input  logic debug_dmactive,
        output logic debug_dmactiveAck
    );

        assign top_clock = clock;

        logic sync_debug_ndreset;
        AsyncResetRegVec_w1_i0_tb debug_ndreset_sync (
            .clock(clock),
            .reset(io_reset),
            .io_d (debug_ndreset),
            .io_q (sync_debug_ndreset)
        );
        assign top_reset                     = io_reset | sync_debug_ndreset;
        assign top_resetctrl_hartIsInReset_0 = top_reset;

        assign debug_systemjtag_reset        = io_debug_reset;
        logic sync_io_debug_reset;
        AsyncResetSynchronizerShiftReg_w1_d3_i0_tb io_debug_reset_shift_sync (
            .clock(clock),
            .reset(io_debug_reset),
            .io_q (sync_io_debug_reset)
        );
        assign debug_reset = ~sync_io_debug_reset;

        ResetSynchronizerShiftReg_w1_d3_i0_tb dmactiveAck_sync (
            .clock(clock),
            .reset(debug_reset),
            .io_d (debug_dmactive),
            .io_q (debug_dmactiveAck)
        );

        logic clock_en;
        always @(posedge clock or posedge debug_reset) begin
            if (debug_reset) begin
            clock_en <= 1'h1;
            end else begin
            clock_en <= debug_dmactiveAck;
            end
        end

        EICG_wrapper gated_clock_debug_clock_gate (
            .in     (clock),
            .test_en(1'b0),
            .en     (clock_en),
            .out    (debug_clock)
        );

    endmodule

    module EICG_wrapper (
        output out,
        input  en,
        input  test_en,
        input  in
    );

        reg en_latched  /*verilator clock_enable*/;

        always @(*) begin
            if (!in) begin
            en_latched = en || test_en;
            end
        end

        assign out = en_latched && in;

    endmodule

    module AsyncResetRegVec_w1_i0_tb (
        input  clock,
        input  reset,
        input  io_d,   // @[repo/rocket-chip/src/main/scala/util/AsyncResetReg.scala 59:14]
        output io_q    // @[repo/rocket-chip/src/main/scala/util/AsyncResetReg.scala 59:14]
    );
        reg reg_;  // @[repo/rocket-chip/src/main/scala/util/AsyncResetReg.scala 61:50]
        assign io_q = reg_;  // @[repo/rocket-chip/src/main/scala/util/AsyncResetReg.scala 65:8]
        always @(posedge clock or posedge reset) begin
            if (reset) begin  // @[repo/rocket-chip/src/main/scala/util/AsyncResetReg.scala 62:16]
            reg_ <= 1'h0;  // @[repo/rocket-chip/src/main/scala/util/AsyncResetReg.scala 63:9]
            end else begin
            reg_ <= io_d;  // @[repo/rocket-chip/src/main/scala/util/AsyncResetReg.scala 61:50]
            end
        end
    endmodule

    module AsyncResetSynchronizerShiftReg_w1_d3_i0_tb (
        input  clock,
        input  reset,
        output io_q    // @[repo/rocket-chip/src/main/scala/util/ShiftReg.scala 36:14]
    );
        wire output_chain_clock;
        wire output_chain_reset;
        wire output_chain_io_d; 
        wire output_chain_io_q; 
        AsyncResetSynchronizerPrimitiveShiftReg_d3_i0_tb output_chain (
            .clock(output_chain_clock),
            .reset(output_chain_reset),
            .io_d (output_chain_io_d),
            .io_q (output_chain_io_q)
        );
        assign io_q = output_chain_io_q;
        assign output_chain_clock = clock;
        assign output_chain_reset = reset;
        assign output_chain_io_d = 1'h1;
    endmodule

    module AsyncResetSynchronizerPrimitiveShiftReg_d3_i0_tb (
        input  clock,
        input  reset,
        input  io_d,
        output io_q 
    );
        reg sync_0;  // @[repo/rocket-chip/src/main/scala/util/SynchronizerReg.scala 51:87]
        reg sync_1;  // @[repo/rocket-chip/src/main/scala/util/SynchronizerReg.scala 51:87]
        reg sync_2;  // @[repo/rocket-chip/src/main/scala/util/SynchronizerReg.scala 51:87]
        assign io_q = sync_0;  // @[repo/rocket-chip/src/main/scala/util/SynchronizerReg.scala 59:8]
        always @(posedge clock or posedge reset) begin
            if (reset) begin  // @[repo/rocket-chip/src/main/scala/util/SynchronizerReg.scala 51:87]
            sync_0 <= 1'h0;  // @[repo/rocket-chip/src/main/scala/util/SynchronizerReg.scala 51:87]
            end else begin
            sync_0 <= sync_1;  // @[repo/rocket-chip/src/main/scala/util/SynchronizerReg.scala 57:10]
            end
        end
        always @(posedge clock or posedge reset) begin
            if (reset) begin  // @[repo/rocket-chip/src/main/scala/util/SynchronizerReg.scala 51:87]
            sync_1 <= 1'h0;  // @[repo/rocket-chip/src/main/scala/util/SynchronizerReg.scala 51:87]
            end else begin
            sync_1 <= sync_2;  // @[repo/rocket-chip/src/main/scala/util/SynchronizerReg.scala 57:10]
            end
        end
        always @(posedge clock or posedge reset) begin
            if (reset) begin  // @[repo/rocket-chip/src/main/scala/util/SynchronizerReg.scala 54:22]
            sync_2 <= 1'h0;
            end else begin
            sync_2 <= io_d;
            end
        end
    endmodule

    module ResetSynchronizerShiftReg_w1_d3_i0_tb (
        input  clock,
        input  reset,
        input  io_d,
        output io_q 
    );
        wire output_chain_clock;
        wire output_chain_reset;
        wire output_chain_io_d; 
        wire output_chain_io_q; 
        AsyncResetSynchronizerPrimitiveShiftReg_d3_i0_tb output_chain (
            .clock(output_chain_clock),
            .reset(output_chain_reset),
            .io_d (output_chain_io_d),
            .io_q (output_chain_io_q)
        );
        assign io_q = output_chain_io_q;
        assign output_chain_clock = clock;
        assign output_chain_reset = reset;
        assign output_chain_io_d = io_d;
    endmodule

至此代码核内的代码部分已经实现完毕了。

处理器测试
~~~~~~~~~~~~~~~~~~~

因为这部分代码不开源，所以我只能提供一个简单的思路。

功能测试
----------------------

首先我们执行了香山提供的三个测试：

* print hello world：测试外围的串口正确，测试 flash 读写正确
* memory copy：测试内存读写正确
* thread switch：测试时钟中断正确

全都执行通过后进行功能测试，我们将 starship 的 regvault 分支的 function test 移植过来，将起始地址设置为 0x30000000，然后开始测试。因为不支持差分测试，对于结果只能根据调试信息人工比对。测试通过说明我们新增的 regvault 扩展没有问题。

JTAG 测试
-----------------------

之后执行 jtag 的测试，我们在仿真环境中加入 SimJTAG 模块，将 Top 的 JTAG 信号连接到 SimJTAG，然后用 riscv-spike-sdk 的 openocd、sdk 进行连接和调试，对 debug 的断点、单步、内存读写、寄存器读写进行测试。

设置断点其实是在存储器中写入 ebreak 指令，然后在执行的时候触发异常，然后陷入 debug rom 等待后续指令，因此我们不能再 flash 打断点（flash 不可写），因此我们只能在 memory 打断点。我们首先编写一个在将 flash 程序拷贝到内存，然后在内存执行程序的程序，然后执行如下操作流程：

* 设置内存写监视器，watch 0x80000080
* 执行程序，当写了 0x80000080 的时候会断住
* 这个时候 0x80000000 的指令已经写好了，打 0x80000000 的断点
* 执行 continue，等再次断住，这个时候程序已经被拷贝到内存，然后可以开始正常的调试

不过实际上我们也可以直接 hook 模拟的 memory，让他直接载入程序对应的 hex 文件，略过拷贝的过程，节约仿真测试的时间。

这个方法可以在外部存储拷贝到内存的启动阶段的时候设置断点，当我们需要对一个芯片启动阶段进行调试的时候，就可以这样操作。

不过因为我们下板子之后，内存拷贝比较慢，当我们启动 debug module 连接让 hart 陷入 debug rom 的时候做了一半的外部存储的拷贝，这个时候 0x80000000 已经拷贝完毕，可以直接打断点。

如果芯片的内存拷贝非常快，导致还没 openocd 连接，已经拷贝完毕开始执行后续程序了，这个时候我们可以在被拷贝的程序开头加入一个死循环，这样程序拷贝完毕之后会死循环，在 openocd 连接之后执行 set PC 等指令跳出死循环就可以执行后续操作。

可能是因为仿真过于慢的问题，在执行 debug 的时候会出现 package error，然后执行一些指令会遇到 ``Invalid remote reply: b0a2b600``，多次执行才可以解决。但是暂时无法定位问题发生的原因。

指令测试
------------------------

用 riscv-tests 生成所有指令的测试程序，然后让处理器依次执行，看是不是可以测试成功。

步骤如下：

* 修改 env 的 macro，让程序的执行地址和处理器保持一致
* hook 处理器模拟的 memory，让处理器可以直接将程序载入内存，节约从 flash 拷贝的时间
* 因为没有 to_host 的检查，在 write_host 之后加入一条 read_host，然后对硬件做 hook，检查读 host 地址的时候对应的值是不是 1（替换原来的 host 写入 1 结束的 pass 条件）
* 编写 Python 脚本让处理器自动化的执行各个测试

这三部分测试和仿真环境因为设计香山的技术，所以保持闭源。

内核启动测试
-------------------

没有真的执行，理论上应该让处理器执行完整的内核。

但是我们没有香山外围的设备树，所以没有办法实现最后的系统镜像，这部分等后续有机会弥补。