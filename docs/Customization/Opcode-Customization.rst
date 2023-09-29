.. _opcode:

RISC-V Opcode Customization
===========================

RISC-V is designed to be highly modular and customizable, allowing designers to create custom processor implementations tailored to specific applications and requirements.
The modularity of RISC-V comes from its encoding scheme, which divides instructions into different groups and provides various optional extensions that can be added to the base ISA.
RISC-V provides a "reserved" opcode space, which allows you to create custom instructions.

.. pdfview:: ../_pdf/unpriv-isa-asciidoc.pdf 131
  :align: center
  :name: custom_opcode_space
  :left: 0.074
  :upper: 0.218
  :right: 0.926
  :lower: 0.462
  
  Unprivileged ISA Specification, Table 35

From the :numref:`custom_opcode_space`, we can find that the reserved opcodes for custom instructions are *custom-0* (``0b000_1011``) and *custom-1* (``0b010_1011``).
