from brewpi.connector.controlbox.system_id import SystemID
from brewpi.connector.controlbox.time import CurrentTicks, ValueProfile
from controlbox.classes import ElapsedTime

# Now comes the application-specific objects.
from controlbox.controller import TypedControlbox, EncoderDecoderDefinition, ReadWriteValue, ForwardingEncoder, \
    ForwardingDecoder, BufferDecoder, ReadWriteUserObject, ShortEncoder, ShortDecoder, ControlboxObject, \
    DynamicContainer, BufferEncoder, ObjectTypeMapper
from controlbox.protocol.controlbox import encode_id, decode_id


class BrewpiController(TypedControlbox):

    def initialize(self, load_profile=True):
        super().initialize(load_profile)
        # id_obj = self.system_id()
        # current_id = id_obj.read()
        # for managing the ID in the python layer for controllers that don't have their own
        # guaranteed unique ID.  Not required for Particle devices.
        # if int(current_id[0]) == 0xFF:
        #     current_id = fetch_id()
        #     id_obj.write(current_id)

    def system_id(self) -> SystemID:
        return SystemID(self, self._sysroot, 0, 12)

    def system_time(self) -> ElapsedTime:
        # todo - would be cleaner if we used cached instance rather than
        # creating a new instance each time
        return ElapsedTime(self, self._sysroot, 1)


class PersistentValueBase(EncoderDecoderDefinition, ReadWriteValue, ForwardingEncoder, ForwardingDecoder):
    """ This is split into a base class to support system and user persisted values. The default value type is
        a buffer. This can be changed by setting the encoder and decoder attributes. """
    decoder = BufferDecoder()
    encoder = BufferEncoder()

    def encoded_len(self):
        return 0  # not known


class PersistentValue(PersistentValueBase, ReadWriteUserObject):
    """ A user persistent value. """
    type_id = 5

    def write_mask(self, value, mask):
        """ Allows a partial update of the value via a masked write. Wherever the mask bit has is set, the corresponding
            bit from value is written.
        """
        return self.controller.write_masked_value(self, (value, mask))


class PersistentShortValue(PersistentValue):
    decoder = ShortDecoder()
    encoder = ShortEncoder()


class LogicActuator:
    type_id = 7


class BangBangController:
    type_id = 8


class PersistChangeValue(ReadWriteUserObject, ShortEncoder, ShortDecoder, ReadWriteValue):
    """ A persistent value in the controller. The value is persisted when it the amount it changes from the
    last persisted value passes a certain threshold.
    Definition args: a tuple of (initial value:signed 16-bit, threshold: unsigned 16-bit). """
    type_id = 9
    shortEnc = ShortEncoder()
    shortDec = ShortDecoder()

    @classmethod
    def encode_definition(cls, arg):
        if arg[1] < 0:
            raise ValueError("threshold < 0")
        return cls.shortEnc.encode(arg[0]) + cls.shortEnc.encode(arg[1])

    @classmethod
    def decode_definition(cls, data_block: bytes, *args, **kwargs):
        return cls.shortDec.decode(data_block[0:2]), cls.shortDec.decode(data_block[2:4])


class IndirectValue(ReadWriteUserObject):
    type_id = 0x0D

    @classmethod
    def encode_definition(cls, value: ControlboxObject):
        return encode_id(value.id_chain)

    @classmethod
    def decode_definition(cls, buf, controller, *args, **kwargs):
        id_chain = decode_id(buf)
        return controller.object_at(id_chain)

    def encoded_len(self):
        return self.definition.encoded_len()

    def decode(self, buf):
        return self.definition.decode(buf)

    def encode(self, value):
        return self.definition.encode(value)


class BuiltInObjectTypes(ObjectTypeMapper):
    # for now, we assume all object types are instantiable. This is not strictly always the case, e.g. system objects
    # that are pre-instantiated may still need to be referred to by type. Will
    # tackle this when needed.

    def all_types(self):
        return (CurrentTicks, DynamicContainer, PersistentValue, ValueProfile, LogicActuator, BangBangController,
                PersistChangeValue, IndirectValue)


class MixinController(BrewpiController):

    def __init__(self, connector, objectTypes=None):
        super().__init__(connector, objectTypes or BuiltInObjectTypes())

    def create_current_ticks(self, container=None, slot=None) -> CurrentTicks:
        return self.create_object(CurrentTicks, None, container, slot)

    def create_dynamic_container(self, container=None, slot=None) -> DynamicContainer:
        return self.create_object(DynamicContainer, None, container, slot)

    def disconnect(self):
        """ forces the underlying connection with the controller to be disconnected. """
        self._connector.disconnect()


class CrossCompileController(MixinController):
    """ additional options only available on the cross-compile """

    def __init__(self, connector):
        super().__init__(connector)


class ArduinoController(MixinController):

    def __init__(self, connector):
        super().__init__(connector)
