from pollination_dsl.dag import Inputs, DAG, task, Outputs
from dataclasses import dataclass
from pollination.two_phase_daylight_coefficient import TwoPhaseDaylightCoefficientEntryPoint
from pollination.honeybee_radiance_postprocess.leed import DaylightOptionOne

# input/output alias
from pollination.alias.inputs.model import hbjson_model_grid_input
from pollination.alias.inputs.wea import wea_input_timestep_check
from pollination.alias.inputs.north import north_input
from pollination.alias.inputs.radiancepar import rad_par_annual_input
from pollination.alias.inputs.grid import grid_filter_input, \
    min_sensor_count_input, cpu_count
from pollination.alias.outputs.daylight import leed_one_credit_summary_results, \
    leed_one_ase_hours_above_results, daylight_autonomy_results, \
    leed_one_hourly_pct_above_results, leed_one_shade_transmittance_results


@dataclass
class LeedDaylightOptionIEntryPoint(DAG):
    """LEED daylight option I entry point."""

    # inputs
    north = Inputs.float(
        default=0,
        description='A number for rotation from north.',
        spec={'type': 'number', 'minimum': 0, 'maximum': 360},
        alias=north_input
    )

    cpu_count = Inputs.int(
        default=50,
        description='The maximum number of CPUs for parallel execution. This will be '
        'used to determine the number of sensors run by each worker.',
        spec={'type': 'integer', 'minimum': 1},
        alias=cpu_count
    )

    min_sensor_count = Inputs.int(
        description='The minimum number of sensors in each sensor grid after '
        'redistributing the sensors based on cpu_count. This value takes '
        'precedence over the cpu_count and can be used to ensure that '
        'the parallelization does not result in generating unnecessarily small '
        'sensor grids. The default value is set to 1, which means that the '
        'cpu_count is always respected.', default=500,
        spec={'type': 'integer', 'minimum': 1},
        alias=min_sensor_count_input
    )

    radiance_parameters = Inputs.str(
        description='The radiance parameters for ray tracing.',
        default='-ab 2 -ad 5000 -lw 2e-05 -dr 0',
        alias=rad_par_annual_input
    )

    grid_filter = Inputs.str(
        description='Text for a grid identifier or a pattern to filter the sensor grids '
        'of the model that are simulated. For instance, first_floor_* will simulate '
        'only the sensor grids that have an identifier that starts with '
        'first_floor_. By default, all grids in the model will be simulated.',
        default='*',
        alias=grid_filter_input
    )

    model = Inputs.file(
        description='A Honeybee Model JSON file (HBJSON) or a Model pkl (HBpkl) file. '
        'This can also be a zipped version of a Radiance folder, in which case this '
        'recipe will simply unzip the file and simulate it as-is.',
        extensions=['json', 'hbjson', 'pkl', 'hbpkl', 'zip'],
        alias=hbjson_model_grid_input
    )

    wea = Inputs.file(
        description='Wea file.',
        extensions=['wea'],
        alias=wea_input_timestep_check
    )

    shade_transmittance = Inputs.float(
        description='A value to use as a multiplier in place of solar shading. Value '
        'for shade transmittance must be 1 > value > 0.', default=0.05
    )

    shade_transmittance_file = Inputs.file(
        description='A JSON file with a dictionary where aperture groups are keys, and '
        'the value for each key is the shade transmittance. Values for shade '
        'transmittance must be 1 > value > 0.',
        path='shade_transmittance.json', extensions=['json'], optional=True
    )

    @task(
        template=TwoPhaseDaylightCoefficientEntryPoint
    )
    def run_two_phase_daylight_coefficient(
            self, north=north, cpu_count=cpu_count, min_sensor_count=min_sensor_count,
            radiance_parameters=radiance_parameters, grid_filter=grid_filter,
            model=model, wea=wea
    ):
        pass    

    @task(
        template=DaylightOptionOne,
        needs=[run_two_phase_daylight_coefficient]
    )
    def leed_daylight_option_one(
        self, folder='results', grid_filter=grid_filter,
        shade_transmittance=shade_transmittance,
        shd_transmittance_file=shade_transmittance_file, model=model
    ):
        return [
            {
                'from': DaylightOptionOne()._outputs.leed_summary,
                'to': 'leed_summary'
            }
        ]

    results = Outputs.folder(
        source='results', description='Folder with raw result files (.ill) that '
        'contain illuminance matrices for each sensor at each timestep of the analysis.'
    )

    leed_summary = Outputs.folder(
        source='leed_summary', description='LEED summary folder.'
    )

    credit_summary = Outputs.file(
        description='JSON file containing the number of LEED credits achieved and '
        'sDA and ASE for the whole space combined.',
        source='leed_summary/summary.json',
        alias=leed_one_credit_summary_results
    )

    space_summary = Outputs.file(
        description='JSON file containing the sDA and ASE for each space.',
        source='leed_summary/summary_grid.json'
    )

    dynamic_schedule = Outputs.file(
        description='JSON file containing the dynamic schedule of shade '
        'transmittance values for each hour.',
        source='leed_summary/states_schedule.json',
        alias=leed_one_shade_transmittance_results
    )

    dynamic_schedule_err = Outputs.file(
        description='JSON file containing the hours at which no shading combination '
        'pass the 2% rule if any.',
        source='leed_summary/states_schedule_err.json'
    )

    daylight_autonomy = Outputs.folder(
        description='Daylight Autonomy results with the shade transmittance '
        'following the 2% rule.',
        source='leed_summary/results/da',
        alias=daylight_autonomy_results
    )

    ase_hours_above = Outputs.folder(
        description='The number of hours where the direct illuminance is 1000 lux '
        'or higher.',
        source='leed_summary/results/ase_hours_above',
        alias=leed_one_ase_hours_above_results
    )

    hourly_percentage_above = Outputs.folder(
        description='The hourly percentage of floor area where the direct illuminance '
        'is 1000 lux or higher.',
        source='leed_summary/datacollections/ase_percentage_above',
        alias=leed_one_hourly_pct_above_results
    )
