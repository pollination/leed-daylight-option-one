from pollination_dsl.dag import Inputs, DAG, task, Outputs
from dataclasses import dataclass
from pollination.honeybee_radiance.multiphase import AddApertureGroupBlinds
from pollination.two_phase_daylight_coefficient import TwoPhaseDaylightCoefficientEntryPoint
from pollination.honeybee_radiance_postprocess.leed import DaylightOptionOne

# input/output alias
from pollination.alias.inputs.model import hbjson_model_room_input
from pollination.alias.inputs.wea import wea_input_timestep_annual_check
from pollination.alias.inputs.north import north_input
from pollination.alias.inputs.radiancepar import rad_par_annual_input
from pollination.alias.inputs.grid import grid_filter_input, cpu_count
from pollination.alias.outputs.daylight import leed_one_credit_summary_results, \
    leed_one_summary_grid_results, leed_one_ase_hours_above_results, \
    daylight_autonomy_results, leed_one_hourly_pct_above_results, \
    leed_one_shade_transmittance_results

from ._visualization import DaylightOptionOneVisualization


@dataclass
class LeedDaylightOptionIEntryPoint(DAG):
    """LEED daylight option I entry point."""

    # inputs
    north = Inputs.float(
        default=0,
        description='A number between -360 and 360 for the counterclockwise '
        'difference between the North and the positive Y-axis in degrees. This '
        'can also be a Vector for the direction to North. (Default: 0).',
        spec={'type': 'number', 'minimum': -360, 'maximum': 360},
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
        'sensor grids.',
        default=1000, default_local=500,
        spec={'type': 'integer', 'minimum': 1}
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
        alias=hbjson_model_room_input
    )

    wea = Inputs.file(
        description='Wea or EPW file. This must be an hourly weather file with annual '
        'data.',
        extensions=['wea', 'epw'],
        alias=wea_input_timestep_annual_check
    )

    diffuse_transmission = Inputs.float(
        default=0.05,
        description='Diffuse transmission of the aperture group blinds. Default '
        'is 0.05 (5%).',
        spec={'type': 'number', 'minimum': 0.0001, 'maximum': 1}
    )

    specular_transmission = Inputs.float(
        default=0.0001,
        description='Specular transmission of the aperture group blinds. Default '
        'is 0 (0%).',
        spec={'type': 'number', 'minimum': 0.0001, 'maximum': 1}
    )

    @task(template=AddApertureGroupBlinds)
    def add_aperture_group_blinds(
        self, model=model, diffuse_transmission=diffuse_transmission,
        specular_transmission=specular_transmission
    ):
        return [
            {
                'from': AddApertureGroupBlinds()._outputs.output_model,
                'to': 'output_model.hbjson'
            }
        ]


    @task(
        template=TwoPhaseDaylightCoefficientEntryPoint,
        needs=[add_aperture_group_blinds]
    )
    def run_two_phase_daylight_coefficient(
            self, north=north, cpu_count=cpu_count, min_sensor_count=min_sensor_count,
            radiance_parameters=radiance_parameters, grid_filter=grid_filter,
            model=add_aperture_group_blinds._outputs.output_model, wea=wea
    ):
        pass

    @task(
        template=DaylightOptionOne,
        needs=[run_two_phase_daylight_coefficient]
    )
    def leed_daylight_option_one(
        self, folder='results', grid_filter=grid_filter, model=model,
        blind_postprocess='states'
    ):
        return [
            {
                'from': DaylightOptionOne()._outputs.leed_summary,
                'to': 'leed_summary'
            }
        ]

    @task(
        template=DaylightOptionOneVisualization,
        needs=[run_two_phase_daylight_coefficient, leed_daylight_option_one],
        sub_paths={
            'pass_fail': 'pass_fail'
        }
    )
    def create_visualization(
        self, model=model, pass_fail=leed_daylight_option_one._outputs.leed_summary
    ):
        return [
            {
                'from': DaylightOptionOneVisualization()._outputs.visualization,
                'to': 'visualization.vsf'
            }
        ]

    output_model = Outputs.file(
        source='output_model.hbjson', description='Model with blinds.'
    )

    visualization = Outputs.file(
        source='visualization.vsf',
        description='Visualization in VisualizationSet format.'
    )

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
        source='leed_summary/summary_grid.json',
        alias=leed_one_summary_grid_results
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
