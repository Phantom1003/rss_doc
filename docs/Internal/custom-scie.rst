sycuricon( 七 ): 指令扩展（SCIE 版）
======================================

之前我们介绍了如何用 ROCC 进行处理器的用户自定义指令扩展，现在我们介绍如何用 rocket-chip 的 SCIE 进行指令扩展。

这里我们仍然以 regvault 指令扩展为例子，regvault 指令扩展的细节可以参见“sycuricon( 五 ): 指令扩展（ROCC 版）”。

SCIE 工作机制
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

ROCC 类似于流水线外的单独调用的协处理器，而 SCIE 则是直接集成在流水线流水集当中的处理单元，定位上类似于乘除法器单元。

SCIE 提供了两种计算模式，对应的也会生成两套计算硬件，一种是不允许指令流水化处理的 SCIEUnpipelined，一种是允许指令流水化处理的 SCIEPipelined。
现在我们分别介绍两种 SCIE 接口的流水线机制、接口特性，和如何实现多周期指令 regvault。

SCIEUnpipelined 硬件实现
----------------------------------

一种是不支持流水线计算的 SCIEUnpipelined。
该模块是一个单纯的计算单元，被放置在 EXE 内部，其基本的输入输出的接口定义如下：

.. remotecode:: ../_static/tmp/scie_unpipeline_default_define
	:url: https://github.com/Phantom1003/rocket-chip/blob/025184e1a0fdd8338eb0f66ad9ab33587b619854/src/main/scala/scie/SCIE.scala
	:language: scala
	:type: github-permalink
	:lines: 55-63
	:caption: SCIEUnpipelined 接口定义

可以看到 SCIE 是简单的 R 类型指令格式，在 EXE 阶段接受指令、两个元操作数，返回计算结果。
如果我们的 SCIE 指令功能简单可以单周期实现，我们可以直接用这个接口进行硬件设计，CPI 开销为一个时钟周期。

.. code-block:: text

    +--------+          EXE stage          +---------+    MEM stage    +--------+   WB stage         
    |        |     +-----------------+     |         |                 |        |
    |        |     |                 |     |         |                 |        |
    | ID/EXE |---->| SCIEUnpipelined |---->| EXE/MEM |---------------->| MEM/WB |------------->
    |        |     |                 |     |         |                 |        |
    |        |     +-----------------+     |         |                 |        | 
    +--------+                             +---------+                 +--------+ 

但是因为 regvault 是多周期的，简单的单周期 SCIEUnpipelined 实现没有办法满足 regvault 计算单元硬件实现的需要，
所以我们需要实现多周期的 SCIEUnpipelined。
对应的接口定义如下，valid=1 表示输入有效，ready=1 的时候表示输出有效。

.. remotecode:: ../_static/tmp/scie_unpipeline_multicycle_define
	:url: https://github.com/Phantom1003/rocket-chip/blob/53d8185a0e5cc1258acaccb60a89bfd60cbc58a1/src/main/scala/scie/SCIE.scala
	:language: scala
	:type: github-permalink
	:lines: 43-52
	:caption: SCIEUnpipelined 多周期接口定义

Rocket-chip 并没有常规的 stall 机制。
常规设计的时候，如果我们在 EXE 阶段需要执行多周期，这个时候如果执行没有完成，
我们可以让处理器在 EXE 阶段 stall 直到 SCIE 得到计算结果，再继续执行。
但是 Rocket-chip 采用了另一种 replay 机制。
他只给每个阶段预留了一个周期的执行时间，如果一个周期之后还没有执行完毕，他会记录这条指令执行无效，
需要重新执行，然后 rocket-chip 会在后续重新发射这条指令。

以 SCIE 的 regvault 实现为例子。我们的 SCIEUnpipelined 的一种实现需要 5 个周期从才可以执行完毕。
这个时候 EXE 阶段执行 SCIE 指令，但是本周期无法执行完毕。因此指令会被标记为 replay，然后向后传播信号。
但是 SCIE 内部其实会继续执行这条指令后续的计算。
而 replay 的指令会依次进入 MEM 阶段、WB 阶段，然后控制单元发现指令需要 replay，于是会从 ID 阶段重新发射，然后进入 EXE 阶段。
这个时候 SCIE 过了五个周期已经执行完毕了，所以这次指令在 EXE 检查发现执行完毕了，就不 replay 向后流淌。

具体的可以参看下图：

+-----------+-----------+-----------+-----------+
|     ID    |   EXE     |    MEM    |     WB    |
+-----------+-----------+-----------+-----------+
|           |SCIE idle  |           |           |
| insn issue|           |           |           |
+-----------+-----------+-----------+-----------+
|           |SCIE busy/ |           |           |
|           |insn replay|           |           |
+-----------+-----------+-----------+-----------+
|           |SCIE busy  |           |           |
|           |           |insn replay|           |
+-----------+-----------+-----------+-----------+
|           |SCIE busy  |           |           |
|           |           |           |insn replay|
+-----------+-----------+-----------+-----------+
|           |SCIE busy  |           |           |
|insn issue |           |           |           |
+-----------+-----------+-----------+-----------+
|           |SCIE ready/|           |           |
|           |insn finish|           |           |
+-----------+-----------+-----------+-----------+

这里我们可以看到，如果 SCIE 计算周期是 1, 那么流水线只需要一个周期就可以计算完毕。
但是如果是 2、3、4、5, 那么 SCIE 统一需要 replay 一次，花费 5 个周期。
所以 4k+2 - 4k+5 统一需要 4k + 5 个周期，将 4k+5 的周期优化为 4k+2 在不做其他修改的前提下，没有意义。

.. remotecode:: ../_static/tmp/scie_unpipeline_pipeline_link
	:url: https://github.com/Phantom1003/rocket-chip/blob/53d8185a0e5cc1258acaccb60a89bfd60cbc58a1/src/main/scala/rocket/RocketCore.scala
	:language: scala
	:type: github-permalink
	:lines: 392-401
	:caption: SCIEUnpipelined 流水线连接

SCIEUnpipelined 在 valid=1 的时候开始执行计算，然后在计算结束之后将数据保存到缓存当中，然后将 ready 设置为 1。
之所以需要设置缓存，是因为当结果计算完毕之后，
当前阶段的 EXE 不一定正好在重新执行对应的指令，所以这个结果需要保存起来，等待被流水线接收。
虽然 SCIEUnpipelined 对外只有一个简单的 ready 信号和 valid 信号，
但是因为 SCIE 指令都是顺序执行的，所以向 SCIE 发送的请求和流水线的请求都是保序的，
SCIE 只需要在上一条指令没有提交之前，不响应下一条指令的请求即可。
此外因为 replay 机制的存在，SCIE 可能多次受到同一个请求，
这个时候检查输入是否保存一致（也就是是否为同一个请求），
防止对一个请求做多次处理，对于流水线而言一个输入如果会产生多个时序的输出，那就会造成问题。

.. remotecode:: ../_static/tmp/scie_unpipeline_pipeline_link
	:url: https://github.com/Phantom1003/rocket-chip/blob/53d8185a0e5cc1258acaccb60a89bfd60cbc58a1/src/main/scala/rocket/RocketCore.scala
	:language: scala
	:type: github-permalink
	:lines: 498-504
	:caption: SCIEUnpipelined replay

SCIE 内部的实现和 ROCC 没有本质区别，就不过多赘述了，大家可以自行参考代码。

SCIEPipelined 实现
---------------------------------

SCIEPipelined 计算单元是横亘 EXE、MEM 两个阶段的二阶段流水线。
他在 EXE 阶段接受计算参数，然后预期在下个时钟周期从 MEM 阶段得到计算结果。
相对于 SCIEUnpipelined 来说，SCIEPipelined 有两个好处：

* 对于 2 周期的计算，SCIEUnpipelined 因为 replay 机制的存在，他的 CPI 是 5；但是 SCIEPipelined 可以是 1
* SCIEUnpipelined 一次只能处理一条指令；而 SCIEPipelined 可以流水化处理两条指令；连续指令的 CPI 也是 1
* 当然，如果计算需要 3～6 个周期，那么因为 replay 的存在，SCIEPipelined 也需要 6 个周期

.. code-block:: text     
                            

    +--------+    EXE stage    +---------+    MEM stage    +--------+   WB stage         
    |        |                 |         |                 |        |
    |        |                 |         |                 |        |
    | ID/EXE |-----------++--->| EXE/MEM |---------------->| MEM/WB |------------->
    |        |           ||    |         |    /\           |        |
    |        |           ||    |         |   /||\          |        | 
    +--------+          \||/   +---------+    ||           +--------+ 
                         \/                   ||
                  +-----------------+---------++------+     
                  |                 |                 |     
                  | SCIEpipelined1  | SCIEpipelined2  |
                  |                 |                 |     
                  +-----------------+-----------------+

具体实现和单周期的 SCIE 大同小异，就是利用一下两阶段流水线就好了。

译码部件
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

object SCIE 定义指令的 opcode 等各类参数；SCIEDecoder 对输入的指令进行译码，
决定指令是由 SCIEUnpipelined 执行（io.unpipeline==true）还是 SCIEPipelined（io.pipeline==true）。
SCIE 的译码并没有被紧耦合到 decoder 当中，估计是为了更好的封装在 SCIE 接口内部。

.. remotecode:: ../_static/tmp/scie_unpipeline_multicycle_define
	:url: https://github.com/Phantom1003/rocket-chip/blob/53d8185a0e5cc1258acaccb60a89bfd60cbc58a1/src/main/scala/scie/SCIE.scala
	:language: scala
	:type: github-permalink
	:lines: 23-41
	:caption: SCIEDecoder 定义
                             
.. code-block:: text

                             +-----------------+     
                             |                 |     
                        +--->| SCIEUnpipelined |
                        |    |                 |     
        io.unpipeline   |    +-----------------+
                        |       /\       ||
                    +---+----+ /||\      ||    +---------+                 +--------+      
    +------+        |        |  ||      \||/   |         |                 |        |
    |      +------->|        |  ||       \/    |         |                 |        |
    | SCIE |        | ID/EXE |--++-------++--->| EXE/MEM |---------------->| MEM/WB |------------->
    |      +------->|        |           ||    |         |    /\           |        |
    +------+        |        |           ||    |         |   /||\          |        | 
                    +---+----+          \||/   +---------+    ||           +--------+ 
                        |                \/                   ||
            io.pipeline |         +-----------------+---------++------+     
                        |         |                 |                 |     
                        +-------->| SCIEpipelined1  | SCIEpipelined2  |
                                  |                 |                 |     
                                  +-----------------+-----------------+

SCIE 和 ROCC 的比较
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

从性能上来说，SCIE 的性能比 ROCC 要高很多：

* SCIE 位于处理器流水线内部，指令进入 SCIE 模块不需要额外的握手和处理；但是 ROCC 位于处理器流水线之外，需要做额外的握手和同步
* SCIE 因为是在处理器 EXE、MEM 阶段，所以执行结果可以很快的 forward 给其他的处理器流水级；但是 ROCC 为了流水线末端，计算结果必须提交给 regfile 才可以给后续指令，导致后续指令在有数据依赖的时候会一直处于等待状态

从实现上来说，ROCC 的模块化程度更高，但是隔离太绝对：

* SCIE 因为位于流水线内部，是实现紧耦合的，不利于后期维护，所以已经被 rocket 上游砍掉了；ROCC 是独立的模块，可以独立于处理器设计，便于维护
* 但是 ROCC 和流水线内部的同步比较差，比如如果处理器内部的 CSR 修改了，ROCC 也许很难同步 CSR 信息；ROCC 也没法向处理器发送异常信号

