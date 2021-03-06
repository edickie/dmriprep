"""Orchestrating the dMRI-preprocessing workflow."""
from nipype.pipeline import engine as pe
from nipype.interfaces import utility as niu

from niworkflows.engine.workflows import LiterateWorkflow as Workflow
from ... import config
from ...interfaces.vectors import CheckGradientTable
from .util import init_dwi_reference_wf
from .outputs import init_reportlets_wf


def init_dwi_preproc_wf(dwi_file):
    """
    This workflow controls the diffusion preprocessing stages of *dMRIPrep*.

    Workflow Graph
        .. workflow::
            :graph2use: orig
            :simple_form: yes

            from dmriprep.config.testing import mock_config
            from dmriprep import config
            from dmriprep.workflows.dwi.base import init_dwi_preproc_wf
            with mock_config():
                dwi_file = config.execution.bids_dir / 'sub-THP0005' / 'dwi' \
                    / 'sub-THP0005_dwi.nii.gz'
                wf = init_dwi_preproc_wf(str(dwi_file))

    Parameters
    ----------
    dwi_file : str
        dwi NIfTI file

    Inputs
    ------
    dwi_file
        dwi NIfTI file
    bvec_file
        File path of the b-values
    bval_file
        File path of the b-vectors

    Outputs
    -------
    dwi_file
        dwi NIfTI file
    dwi_mask
        dwi mask

    See also
    --------
    * :py:func:`~dmriprep.workflows.dwi.util.init_dwi_reference_wf`
    * :py:func:`~dmriprep.workflows.dwi.outputs.init_reportlets_wf`

    """
    wf_name = _get_wf_name(dwi_file)

    # Build workflow
    workflow = Workflow(name=wf_name)

    # Have some options handy
    layout = config.execution.layout
    omp_nthreads = config.nipype.omp_nthreads
    # freesurfer = config.workflow.run_reconall
    # spaces = config.workflow.spaces

    inputnode = pe.Node(niu.IdentityInterface(
        fields=['dwi_file', 'bvec_file', 'bval_file',
                'subjects_dir', 'subject_id',
                't1w_preproc', 't1w_mask', 't1w_dseg', 't1w_tpms', 't1w_aseg', 't1w_aparc',
                'anat2std_xfm', 'std2anat_xfm', 'template',
                't1w2fsnative_xfm', 'fsnative2t1w_xfm']),
        name='inputnode')
    inputnode.inputs.dwi_file = dwi_file
    inputnode.inputs.bvec_file = layout.get_bvec(dwi_file)
    inputnode.inputs.bval_file = layout.get_bval(dwi_file)

    outputnode = pe.Node(niu.IdentityInterface(
        fields=['out_dwi', 'out_bvec', 'out_bval', 'out_rasb',
                'out_dwi_mask']),
        name='outputnode')

    gradient_table = pe.Node(CheckGradientTable(), name='gradient_table')

    dwi_reference_wf = init_dwi_reference_wf(omp_nthreads=omp_nthreads)

    # MAIN WORKFLOW STRUCTURE
    workflow.connect([
        (inputnode, gradient_table, [
            ('dwi_file', 'dwi_file'),
            ('bvec_file', 'in_bvec'),
            ('bval_file', 'in_bval')]),
        (inputnode, dwi_reference_wf, [('dwi_file', 'inputnode.dwi_file')]),
        (gradient_table, dwi_reference_wf, [('b0_ixs', 'inputnode.b0_ixs')]),
        (dwi_reference_wf, outputnode, [
            ('outputnode.ref_image', 'out_dwi'),
            ('outputnode.dwi_mask', 'out_dwi_mask')]),
        (gradient_table, outputnode, [
            ('out_bvec', 'out_bvec'),
            ('out_bval', 'out_bval'),
            ('out_rasb', 'out_rasb')])
    ])

    # REPORTING ############################################################
    reportlets_dir = str(config.execution.work_dir / 'reportlets')
    reportlets_wf = init_reportlets_wf(reportlets_dir)
    workflow.connect([
        (inputnode, reportlets_wf, [('dwi_file', 'inputnode.source_file')]),
        (dwi_reference_wf, reportlets_wf, [
            ('outputnode.ref_image', 'inputnode.dwi_ref'),
            ('outputnode.dwi_mask', 'inputnode.dwi_mask'),
            ('outputnode.validation_report', 'inputnode.validation_report')]),
    ])
    return workflow


def _get_wf_name(dwi_fname):
    """
    Derive the workflow name for supplied dwi file.

    >>> _get_wf_name('/completely/made/up/path/sub-01_dwi.nii.gz')
    'dwi_preproc_wf'
    >>> _get_wf_name('/completely/made/up/path/sub-01_run-1_dwi.nii.gz')
    'dwi_preproc_run_1_wf'

    """
    from nipype.utils.filemanip import split_filename
    fname = split_filename(dwi_fname)[1]
    fname_nosub = '_'.join(fname.split("_")[1:])
    name = "dwi_preproc_" + fname_nosub.replace(
        ".", "_").replace(" ", "").replace("-", "_").replace("dwi", "wf")

    return name
