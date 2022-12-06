from collections import ChainMap
from .sdx import SiglentSDx, SiglentChannel, InstrumentBase

from qcodes.parameters import Group, GroupParameter

from qcodes.instrument.channel import ChannelList

from qcodes.validators.validators import MultiTypeOr, Numbers, Ints, Enum as EnumVals

from enum import Enum

from typing import Any, Callable, List, Mapping, Set, Tuple

from .parameter import GroupGetParameter


class SiglentSDGChannel(SiglentChannel):
    def __init__(
        self, parent: InstrumentBase, name: str, channel_number: int, **kwargs
    ):
        super().__init__(parent, name, channel_number)
        self._ch_num_prefix = (
            f"C{channel_number}:" if channel_number is not None else ""
        )

        self._add_outp_parameter_group(
            has_poweron_state=kwargs.pop("has_outp_poweron_state", False)
        )

        self._add_bswv_parameter_group(set())

    def _add_outp_parameter_group(self, *, has_poweron_state: bool):
        ch_num_prefix = self._ch_num_prefix
        ch_cmd_prefix = ch_num_prefix + "OUTP"

        outp_group_params: List[GroupParameter] = []
        outp_set_elements: List[str] = []

        self.add_parameter(
            "enabled",
            parameter_class=GroupGetParameter,
            label="Enabled",
            val_mapping={True: "ON", False: "OFF"},
            set_cmd=ch_cmd_prefix + " {}",
        )

        outp_group_params.append(self.enabled)
        outp_set_elements.append("{enabled}")

        self.add_parameter(
            "load",
            parameter_class=GroupGetParameter,
            label="Output load",
            unit="Ω",
            vals=MultiTypeOr(Numbers(50, 1e5), EnumVals("HZ")),
            set_cmd=ch_cmd_prefix + " LOAD,{}",
        )

        outp_group_params.append(self.load)
        outp_set_elements.append("LOAD,{load}")

        if has_poweron_state:
            self.add_parameter(
                "poweron_state",
                parameter_class=GroupGetParameter,
                label="Power-on state",
                val_mapping={
                    False: 0,
                    True: 1,
                },
                set_cmd=ch_cmd_prefix + " POWERON_STATE,{}",
            )
            outp_group_params.append(self.poweron_state)
            outp_set_elements.append("POWERON_STATE,{poweron_state}")

        self.add_parameter(
            "polarity",
            parameter_class=GroupGetParameter,
            label="Polarity",
            val_mapping={
                "normal": "NOR",
                "inverted": "INVT",
            },
            set_cmd=ch_cmd_prefix + " PLRT,{}"
        )
        outp_group_params.append(self.polarity)
        outp_set_elements.append("PLRT,{polarity}")

        def parse_outp(response: str, *, _skip_prefix=len(ch_cmd_prefix) + 1):
            response = response[_skip_prefix:]
            values = response.split(",")
            outp_remap = {
                "LOAD": "load",
                "PLRT": "polarity",
                "POWERON_STATE": "poweron_state",
            }
            res = {"enabled": values[0]}
            for k, v in zip(*2 * [iter(values[1:])]):
                res[outp_remap.get(k, k)] = v
            return res

        self.output_group = Group(
            outp_group_params,
            set_cmd=ch_cmd_prefix + " " + ",".join(outp_set_elements),
            get_cmd=ch_cmd_prefix + "?",
            get_parser=parse_outp,
        )

    def _add_bswv_parameter_group(self, extra_param_set: Set[str]):
        ch_num_prefix = self._ch_num_prefix
        cmd_prefix = ch_num_prefix + "BSWV"
        cmd_prefix_len = len(cmd_prefix)
        get_cmd = ch_num_prefix + "BSWV?"

        identity = lambda x: x

        def extract_bswv_field(
            name: str, *, then: Callable[[str], Any] = identity, else_default=None
        ) -> Callable[[str], Any]:
            def result_func(response: str):
                response = response[cmd_prefix_len + 1 :]
                values = response.split(",")
                for key, value in zip(*2 * [iter(values)]):
                    if key == name:
                        return then(value)
                else:
                    return else_default

            return result_func

        def strip_unit(
            unit: str, *, then: Callable[[str], Any]
        ) -> Callable[[str], Any]:
            len_unit = len(unit)

            def result_func(value: str):
                if value.endswith(unit):
                    value = value[:-len_unit]
                return then(value)

            return result_func

        self.add_parameter(
            "wave_type",
            label="Basic Wave type",
            val_mapping={
                "sine": "SINE",
                "square": "SQUARE",
                "ramp": "RAMP",
                "pulse": "PULSE",
                "noise": "NOISE",
                "arb": "ARB",
                "dc": "DC",
                "prbs": "PRBS",
                "iq": "IQ",
            },
            set_cmd=cmd_prefix + " WVTP,{}",
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("WVTP"),
        )

        ranges: Mapping[str, Tuple[float, float]] = self._parent._ranges

        freq_ranges = ranges["frequency"]
        amp_range_vpp = ranges["vpp"]
        amp_range_vrms = ranges["vrms"]
        range_offset = ranges["offset"]

        self.add_parameter(
            "frequency",
            label="Basic Wave Frequency",
            vals=Numbers(freq_ranges[0], freq_ranges[1]),
            unit="Hz",
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("FRQ", then=strip_unit("HZ", then=float)),
            set_cmd=cmd_prefix + " FRQ,{}",
        )

        self.add_parameter(
            "period",
            label="Basic Wave Period",
            vals=Numbers(1 / freq_ranges[1], 1 / freq_ranges[0]),
            unit="s",
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("PERI", then=strip_unit("S", then=float)),
            set_cmd=cmd_prefix + " PERI,{}",
        )

        self.add_parameter(
            "amplitude",
            label="Basic Wave Amplitude (Peak-to-Peak)",
            vals=Numbers(amp_range_vpp[0], amp_range_vpp[1]),
            unit="V",
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("AMP", then=strip_unit("V", then=float)),
            set_cmd=cmd_prefix + " AMP,{}",
        )

        self.add_parameter(
            "amplitude_rms",
            label="Basic Wave Amplitude (RMS)",
            vals=Numbers(amp_range_vrms[0], amp_range_vrms[1]),
            unit="V",
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("AMPRMS", then=strip_unit("V", then=float)),
            set_cmd=cmd_prefix + " AMPRMS,{}",
        )

        # doesn't seem to work
        self.add_parameter(
            "amplitude_dbm",
            label="Basic Wave Amplitude (dBm)",
            vals=Numbers(),
            unit="dBm",
            #get_cmd=get_cmd,
            #get_parser=extract_bswv_field("AMPDBM", then=strip_unit("dBm", then=float)),
            set_cmd=cmd_prefix + " AMPDBM,{}",
        )

        self.add_parameter(
            "offset",
            label="Offset",
            vals=Numbers(range_offset[0], range_offset[1]),
            unit="V",
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("OFST", then=strip_unit("V", then=float)),
            set_cmd=cmd_prefix + " OFST,{}",
        )

        self.add_parameter(
            "common_offset",
            label="Common Offset (Differential output)",
            vals=Numbers(-1, 1),
            unit="V",
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("COM_OFST", then=strip_unit("V", then=float)),
            set_cmd=cmd_prefix + " COM_OFST,{}",
        )

        self.add_parameter(
            "ramp_symmetry",
            label="Ramp Symmetry",
            vals=Numbers(0.0, 100.0),
            unit="%",
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("SYM", then=strip_unit("%", then=float)),
            set_cmd=cmd_prefix + " SYM,{}",
        )

        self.add_parameter(
            "duty_cycle",
            label="Duty cycle (Square/Pulse)",
            vals=Numbers(0.0, 100.0),
            unit="%",
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("DUTY", then=strip_unit("%", then=float)),
            set_cmd=cmd_prefix + " DUTY,{}",
        )

        self.add_parameter(
            "phase",
            label="Phase",
            vals=Numbers(0.0, 360.0),
            unit="deg",
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("PHSE", then=float),
            set_cmd=cmd_prefix + " PHSE,{}",
        )

        self.add_parameter(
            "noise_std_dev",
            label="Standard deviation (Noise)",
            vals=Numbers(),
            unit="V",
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("STDEV", then=strip_unit("V", then=float)),
            set_cmd=cmd_prefix + " STDEV,{}",
        )

        self.add_parameter(
            "noise_mean",
            label="Mean (Noise)",
            vals=Numbers(),
            unit="V",
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("MEAN", then=strip_unit("V", then=float)),
            set_cmd=cmd_prefix + " MEAN,{}",
        )

        self.add_parameter(
            "pulse_width",
            label="Pulse width",
            vals=Numbers(min_value=0.0),
            unit="s",
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("WIDTH", then=float),
            set_cmd=cmd_prefix + " WIDTH,{}",
        )

        self.add_parameter(
            "rise_time",
            label="Rise time (Pulse)",
            vals=Numbers(min_value=0.0),
            unit="s",
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("RISE", then=strip_unit("S", then=float)),
            set_cmd=cmd_prefix + " RISE,{}",
        )

        self.add_parameter(
            "fall_time",
            label="Rise time (Pulse)",
            vals=Numbers(min_value=0.0),
            unit="s",
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("FALL", then=strip_unit("S", then=float)),
            set_cmd=cmd_prefix + " FALL,{}",
        )

        self.add_parameter(
            "delay",
            label="Waveform delay",
            vals=Numbers(min_value=0.0),
            unit="s",
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("DLY", then=strip_unit("S", then=float)),
            set_cmd=cmd_prefix + " DLY,{}",
        )

        self.add_parameter(
            "high_level",
            label="High Level",
            vals=Numbers(range_offset[0], range_offset[1]),
            unit="V",
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("HLEV", then=strip_unit("V", then=float)),
            set_cmd=cmd_prefix + " HLEV,{}",
        )

        self.add_parameter(
            "low_level",
            label="Low Level",
            vals=Numbers(range_offset[0], range_offset[1]),
            unit="V",
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("LLEV", then=strip_unit("V", then=float)),
            set_cmd=cmd_prefix + " LLEV,{}",
        )

        self.add_parameter(
            "noise_bandwidth_enabled",
            label="Noise bandwidth enabled",
            val_mapping = {
                False: "OFF",
                True: "ON",
                None: "",
            },
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("BANDSTATE", else_default=""),
            set_cmd=cmd_prefix + " BANDSTATE,{}",
        )

        self.add_parameter(
            "noise_bandwidth",
            label="Noise bandwidth",
            get_cmd=get_cmd,
            vals=Numbers(min_value=0),
            get_parser=extract_bswv_field("BANDWIDTH", then=strip_unit("HZ", then=float)),
            set_cmd=cmd_prefix + " BANDWIDTH,{}",
            unit="Hz",
        )

        self.add_parameter(
            "prbs_length_exp",
            label="PRBS length is (2 ^ x - 1)",
            vals=Ints(3, 32),
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("LENGTH", then=int),
            set_cmd=cmd_prefix + " LENGTH,{}",
        )

        self.add_parameter(
            "prbs_edge_time",
            label="PRBS rise/fall time",
            vals=Numbers(min_value=0),
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("EDGE", then=strip_unit("S", then=float)),
            set_cmd=cmd_prefix + " EDGE,{}",
            unit="s",
        )

        self.add_parameter(
            "differential_mode",
            label="Channel differential output",
            val_mapping = {
                False: "SINGLE",
                True: "DIFFERENTIAL",
            },
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("FORMAT", else_default="SINGLE"),
            set_cmd=cmd_prefix + " FORMAT,{}",
        )

        self.add_parameter(
            "prbs_differential_mode",
            label="PRBS differential mode",
            val_mapping = {
                False: "OFF",
                True: "ON",
            },
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("DIFFSTATE"),
            set_cmd=cmd_prefix + " DIFFSTATE,{}",
        )

        self.add_parameter(
            "prbs_bit_rate",
            label="PRBS bit rate",
            vals=Numbers(min_value=0),
            get_cmd=get_cmd,
            get_parser=extract_bswv_field("BITRATE", then=strip_unit("bps", then=float)),
            set_cmd=cmd_prefix + " BITRATE,{}",
            unit="bps",
        )

        self.add_parameter(
            "prbs_logic_level",
            label="PRBS Logic level",
            val_mapping={
                "ttl": "TTL_CMOS",
                "lvttl": "LVTTL_LVCMOS",
                "cmos": "TTL_CMOS",
                "lvcmos": "LVTTL_LVCMOS",
                "ecl": "ECL",
                "lvpecl": "LVPECL",
                "lvds": "LVDS",
                #"custom": "CUSTOM",
            },
            set_cmd=cmd_prefix + " LOGICLEVEL,{}",
            get_parser=extract_bswv_field("LOGICLEVEL"),
        )


class SiglentSDGx(SiglentSDx):
    def __init__(self, *args, **kwargs):
        n_channels = kwargs.pop("n_channels", None)
        channel_type = kwargs.pop("channel_type", SiglentSDGChannel)
        channel_kwargs = {}
        if kwargs.pop("has_outp_poweron_state", False):
            channel_kwargs["has_outp_poweron_state"] = True
        self._ranges = kwargs.pop("ranges", {})

        super().__init__(*args, **kwargs)

        channels = ChannelList(self, "channel", SiglentSDGChannel, snapshotable=False)

        for channel_number in range(1, n_channels + 1):
            name = f"channel{channel_number}"
            channel = channel_type(self, name, channel_number, **channel_kwargs)
            self.add_submodule(name, channel)
            channels.append(channel)

        self.add_submodule("channel", channels)


class Siglent_SDG_60xx(SiglentSDGx):
    def __init__(self, *args, **kwargs):
        default_params = {
            "n_channels": 2,
            "has_outp_poweron_state": True,
        }
        kwargs = ChainMap(kwargs, default_params)
        super().__init__(*args, **kwargs)


class Siglent_SDG_20xx(SiglentSDGx):
    def __init__(self, *args, **kwargs):
        default_params = {
            "n_channels": 2,
            "has_outp_poweron_state": False,
        }
        kwargs = ChainMap(kwargs, default_params)
        super().__init__(*args, **kwargs)


class Siglent_SDG_6022X(Siglent_SDG_60xx):
    def __init__(self, *args, **kwargs):
        ranges = {
            "frequency": (1e-3, 200e6),
            "vpp": (2e-3, 20.0),
            "vrms": (2e-3, 10.0),
            "offset": (-10, 10),
        }

        kwargs = ChainMap(kwargs, {"ranges": ranges})
        super().__init__(*args, **kwargs)


class Siglent_SDG_2042X(Siglent_SDG_20xx):
    def __init__(self, *args, **kwargs):
        ranges = {
            "frequency": (1e-3, 40e6),
            "vpp": (2e-3, 20.0),
            "vrms": (2e-3, 10.0),
            "offset": (-10, 10),
        }

        kwargs = ChainMap(kwargs, {"ranges": ranges})
        super().__init__(*args, **kwargs)
