.. _opcode:

RISC-V Opcode Customization
===========================

RISC-V is designed to be highly modular and customizable, allowing designers to create custom processor implementations tailored to specific applications and requirements.
The modularity of RISC-V comes from its encoding scheme, which divides instructions into different groups and provides various optional extensions that can be added to the base ISA.
RISC-V provides a "reserved" opcode space, which allows you to create custom instructions.
Althougn you can use any opcodes, to avoid conflicts with future standard extensions, you should use the reserved custom opcode space to create your custom instructions.

.. pdfview:: ../_pdf/unpriv-isa-asciidoc.pdf 131
  :align: center
  :name: custom_opcode_space
  :left: 0.074
  :upper: 0.218
  :right: 0.926
  :lower: 0.462
  
  Unprivileged ISA Specification, Table 35

From the :numref:`custom_opcode_space`, we can find that the reserved opcodes for custom instructions are:

  - **custom-0**: ``0b000_1011``, ``0x0b``
  - **custom-1**: ``0b010_1011``, ``0x2b``
  - **custom-2**: ``0b101_1011``, ``0x5b``
  - **custom-3**: ``0b111_1011``, ``0x7b``

Some projects have already used these custom opcodes, such as Rocket Chip.
Rocket core provides a set of custom instructions, the Rocket Chip Coprocessor (ROCC) instruction extension, for accelerators.

The format of the RoCC instructions follows the R-type format, while the `funct3` part is divided into three bit fields.

.. code-block:: text

   31      25 24  20 19  15 14  13  12  11  7 6    0
  ┌──────────┬──────┬──────┬───┬───┬───┬─────┬──────┐
  │  funct7  │  rs2 │  rs1 │ xd│xs1│xs2│  rd │opcode│
  └──────────┴──────┴──────┴───┴───┴───┴─────┴──────┘

..

  - ``xd`` bit is used to indicate whether the instruction writes a destination register.
  - ``xs1`` and ``xs2`` bits are used to indicate whether the instruction reads source registers.

When the source register and destination register fields are not used, these bits can be used to encode other information, which is really different from the RISC-V standard R-type instruction format.

Here we provide the ROCC example to demonstrate that the format of a custom instruction is not restricted to the standard instruction format. As you create your own custom instruction, you have the freedom to define the format in any way you prefer.
However, it is crucial to thoughtfully and reasonably plan every bit of the instruction format.
When assigning meaning to a bit, it is essential to consider whether it will affect the circuit.

`riscv-opcodes <https://github.com/riscv/riscv-opcodes>`_
---------------------------------------------------------


