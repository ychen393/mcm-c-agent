import streamlit as st
from core.config import get_settings
from core.graph import build_foundation_graph
from core.state import new_research_state
settings = get_settings()
st.set_page_config(page_title=settings.app_name, page_icon='🧮', layout='wide')
st.title('MCM C Research Lab'); st.caption('A semi-autonomous research workspace for MCM Problem C')
with st.sidebar:
    st.subheader('Workspace'); st.info('M0 · Project Foundation'); st.caption(f'Environment: {settings.app_env}'); st.caption(f'LLM provider: {settings.llm_provider}')
left, right = st.columns([1.3, 1])
with left:
    st.subheader('Create a research project'); project_name = st.text_input('Project name', value='MCM C Demo Project'); problem_text = st.text_area('Problem statement', height=180)
    if st.button('Initialize project', type='primary'):
        if len(project_name.strip()) < 3: st.error('Project name must contain at least 3 characters.')
        else:
            state = new_research_state('demo-project', project_name.strip()); state['problem_text'] = problem_text
            st.session_state['last_run'] = build_foundation_graph().invoke(state); st.success('Foundation workflow completed.')
with right:
    st.subheader('System status'); st.metric('Milestone', 'M0'); st.metric('Workflow nodes', '2'); st.metric('Configured provider', settings.llm_provider)
    st.warning('Live LLM calls and persistent checkpoints are not enabled in this foundation demo.')
if 'last_run' in st.session_state: st.subheader('Latest workflow state'); st.json(st.session_state['last_run'])
