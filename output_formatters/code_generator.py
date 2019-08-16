# =================================================================================================
# Copyright (C) 2018-2019 University of Glasgow
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions 
# are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# SPDX-License-Identifier: BSD-2-Clause
# =================================================================================================

from string import ascii_letters

from protocol import *
from output_formatters.outputformatter import OutputFormatter

class CodeGenerator(OutputFormatter):
    """
    Class to generate code from parsed ASCII diagrams - currently only produces Rust
    """

    output: List[str]

    def __init__(self):
        self.output = []
        self.structs = {}

    def generate_output(self):
        pass

    def format_bitstring(self, bitstring:BitString, parent_pt:ProtocolType=None):
        #do bitstrings occur on their own outside of enums/structs?
        if parent_pt == None:
            self.output.append("let %s: u%d;\n" % (bitstring.name.lower(), self.assign_int_size(bitstring)))
        elif parent_pt.kind == "Struct":
            self.output.append(" %s" % bitstring.name)
        elif parent_pt.kind == "Enum":
            self.output.append("    %s(u%d)" % (bitstring.name, self.assign_int_size(bitstring)))

    def assign_int_size(self, bitstring:BitString):
        #assign the smallest possible unsigned int which can accommodate the field
        #TODO: determine how to handle bitstrings which aren't given an explicit size
        if bitstring.size <= 8:
            return 8
        elif bitstring.size <= 16:
            return 16
        elif bitstring.size <= 32:
            return 32
        elif bitstring.size <= 64:
            return 64
        else:
            return 128


    def declare_field_types(self, pt:ProtocolType):
        if pt.kind == "Struct":
            for field in pt.fields:
                #prevent types being declared twice
                if field.field_type.name not in self.output:
                    self.output.append("\n#[derive(Debug")
                    for trait in pt.traits:
                        if trait == "Equality":
                            self.output.append(", PartialEq, Eq")
                        elif trait == "Ordinal":
                            self.output.append(", Ord")
                    self.output.append(")]\n")
                    if field.field_type.kind == "BitString":
                        self.output.extend(["struct ", field.field_type.name, "(u%d);\n" % self.assign_int_size(field.field_type)])
                    elif field.field_type.kind == "Array":
                        if field.field_type.element_type.name not in self.output:
                            self.declare_array_type(field.field_type)
                    elif field.field_type.kind == "Enum":
                        self.format_enum(field.field_type)
                    else:
                        self.output.extend(["struct ", field.field_type.name, ";\n"])
        elif pt.kind == "Array":
            self.declare_array_type(pt)


    def declare_array_type(self, array:Array):
        if array.element_type.kind == "BitString":
            self.output.extend(["struct ", array.element_type.name, "(u%d);\n" % self.assign_int_size(array.element_type)])
        else:
            self.output.extend(["struct ", array.element_type.name, ";\n"])

    def format_struct(self, struct:Struct):
        #declare fields as types first
        self.declare_field_types(struct)
        #traits need to be added up here if we're using !derive (eg. Eq, Ord)
        #including Debug trait by default - this may be changed later
        self.output.append("\n#[derive(Debug")
        for trait in struct.traits:
            if trait == "Equality":
                self.output.append(", PartialEq, Eq")
            elif trait == "Ordinal":
                self.output.append(", Ord")
        self.output.append(")]\n")
        self.output.extend(["struct ", struct.name, " {\n"])
        for field in struct.fields:
            self.output.append("    %s: " % field.field_name)
            if field.field_type.kind == "BitString":
                self.format_bitstring(field.field_type, struct)
            if field.field_type.kind == "Struct":
                #self.format_field_struct(field.field_type)
                self.output.append("%s" % field.field_type.name)
            if field.field_type.kind == "Enum":
                self.output.append(field.field_type.name)
            if field.field_type.kind == "Array":
                self.format_array(field.field_type)
            self.output.append(",\n")
        self.output.append("}\n")

    def format_array(self, array:Array):
        if array.length is None:
            self.output.append("Vec<%s" % array.element_type.name)
            if array.element_type.kind == "BitString":
                self.output.append("(u%d)" % self.assign_int_size(array.element_type))
            self.output.append(">")
        else:
            self.output.append("[%s" % array.element_type.name)
            if array.element_type.kind == "BitString":
                self.output.append("(u%d)" % self.assign_int_size(array.element_type))
            self.output.append("; %d]" % array.length)

    def format_enum(self, enum:Enum):
        for variant in enum.variants:
            if variant.kind == "Struct":
                self.declare_field_types(variant)
        self.output.append("\nenum %s {\n" % enum.name)
        for variant in enum.variants:
            if variant.kind == "BitString":
                self.format_bitstring(variant, enum)
            elif variant.kind == "Struct":
                #self.format_field_struct(variant)
                pass
            elif variant.kind == "Array":
                self.format_array(variant)
            else:
                #TODO: double-check enums which are their own type with no associated value can actually be generated by frontend
                self.append("%s" % variant.name)
            self.output.append(",\n")
        self.output.append("}\n")


    def format_function(self, function:Function):
        pass


    def format_context(self, context:Context):
        pass

    def closure_gen(self):
        for i in range(len(ascii_letters)):
            yield ascii_letters[i]

    def format_parser(self, protocol:Protocol):
        for item in protocol.get_type_names():
            if protocol.get_type(item).kind == "Struct":
                parser_functions = []
                closure_terms = []
                generator = self.closure_gen()
                #write parsers for individual fields
                for field in protocol.get_type(item).fields:
                    if field.field_type == "BitString":
                        self.output.append("\nfn parse_{fname}(input: (&[u8], usize)) -> nom::IResult<(&[u8], usize), {typename}>{{".format(fname=field.field_type.name.lower(), typename=field.field_type.name))
                        self.output.append("\n    map(take({size}_usize), |x| {name}(x))(input)\n}}\n".format(size=field.field_type.size, name=field.field_type.name))
                        if protocol.get_type(item).fields.index(field) != (len(protocol.get_type(item).fields) - 1):
                            parser_functions.append("parse_{name}, ".format(name=field.field_type.name.lower()))
                            closure_terms.append("{term}, ".format(term=next(generator)))
                        else:
                            parser_functions.append("parse_{name}".format(name=field.field_type.name.lower()))
                            closure_terms.append("{term}".format(term=next(generator)))
                #write function to combine parsers to parse an entire PDU
                #TODO: make this use items in PDU field of protocol object, not just list of types (nothing currently in PDUs in test cases)
                self.output.append("\nfn parse_{name}(input: &[u8]) -> nom::IResult<&[u8], {name}>{{".format(name=protocol.get_type(item).name))
                self.output.append("\n    map(bits::<_, _, (_, _), _, _>(tuple(({functions}))), |{closure}|".format(functions="".join(parser_functions), closure="".join(closure_terms)))
                self.output.append(" {struct}{{{values}}})(input)\n}}\n".format(struct=protocol.get_type(item).name, values=zip(iter(protocol.get_type(item).fields), iter(closure_terms))))


    def format_protocol(self, protocol:Protocol):
        #add crate/imports
        self.output.append("extern crate nom;\nuse nom::IResult;\nuse nom::{bits::bits, bits::complete::take, combinator::map};\nuse nom::sequence::tuple;\n\n")
        for item in protocol.get_type_names():
            if protocol.get_type(item).kind == "Struct":
                self.format_struct(protocol.get_type(item))
                self.output.append("\n")
            elif protocol.get_type(item).kind == "Enum":
                self.format_enum(protocol.get_type(item))
                self.output.append("\n")
        self.format_parser(protocol)
        rust_output = "".join(self.output)
        print(rust_output)
        with open("rust_output.rs", "w") as rf:
            rf.write(rust_output)
