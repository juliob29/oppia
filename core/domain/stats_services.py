# coding: utf-8
#
# Copyright 2014 The Oppia Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Services for exploration-related statistics."""

__author__ = 'Sean Lip'

import logging
import sys
import utils

from core.domain import exp_domain
from core.domain import exp_services
from core.domain import interaction_registry
from core.domain import stats_domain
from core.domain import stats_jobs
from core.platform import models
(stats_models,) = models.Registry.import_models([models.NAMES.statistics])
import feconf


IMPROVE_TYPE_DEFAULT = 'default'
IMPROVE_TYPE_INCOMPLETE = 'incomplete'


def get_top_unresolved_answers_for_default_rule(exploration_id, state_name):
    return {
        answer: count for (answer, count) in
        stats_domain.StateRuleAnswerLog.get(
            exploration_id, state_name, exp_domain.DEFAULT_RULESPEC_STR
        ).get_top_answers(3)
    }


def get_state_rules_stats(exploration_id, state_name):
    """Gets statistics for the answer groups and rules of this state.

    Returns:
        A dict, keyed by the string '{HANDLER_NAME}.{RULE_STR}', whose
        values are the corresponding stats_domain.StateRuleAnswerLog
        instances.
    """
    exploration = exp_services.get_exploration_by_id(exploration_id)
    state = exploration.states[state_name]

    # TODO(bhenning): Everything is handler name submit; therefore, it is
    # pointless and should be removed.
    _OLD_SUBMIT_HANDLER_NAME = 'submit'
    rule_keys = []
    for group in state.interaction.answer_groups:
        for rule in group.rule_specs:
            rule_keys.append((
                _OLD_SUBMIT_HANDLER_NAME, rule.stringify_classified_rule()))

    if state.interaction.default_outcome:
        rule_keys.append((
            _OLD_SUBMIT_HANDLER_NAME, exp_domain.DEFAULT_RULESPEC_STR))

    answer_logs = stats_domain.StateRuleAnswerLog.get_multi(
        exploration_id, [{
            'state_name': state_name,
            'rule_str': rule_key[1]
        } for rule_key in rule_keys])

    results = {}
    for ind, answer_log in enumerate(answer_logs):
        results['.'.join(rule_keys[ind])] = {
            'answers': answer_log.get_top_answers(5),
            'rule_hits': answer_log.total_answer_count
        }

    return results


def get_visualizations_info(exploration_id, exploration_version, state_name):
    """Returns a list of visualization info. Each item in the list is a dict
    with keys 'data' and 'options'.
    """
    exploration = exp_services.get_exploration_by_id(exploration_id)
    if exploration.states[state_name].interaction.id is None:
        return []

    visualizations = interaction_registry.Registry.get_interaction_by_id(
        exploration.states[state_name].interaction.id).answer_visualizations

    calculation_ids = list(set([
        visualization.calculation_id for visualization in visualizations]))

    calculation_ids_to_outputs = {}
    for calculation_id in calculation_ids:
        # This is None if the calculation job has not yet been run for this
        # state.
        calc_output_domain_object = (
            stats_jobs.InteractionAnswerSummariesAggregator.get_calc_output(
                exploration_id, exploration_version, state_name, calculation_id))

        # If the calculation job has not yet been run for this state, we simply
        # exclude the corresponding visualization results.
        if calc_output_domain_object is None:
            continue

        calculation_ids_to_outputs[calculation_id] = (
            calc_output_domain_object.calculation_output)

    results_list = [{
        'id': visualization.id,
        'data': calculation_ids_to_outputs[visualization.calculation_id],
        'options': visualization.options,
    } for visualization in visualizations if
        visualization.calculation_id in calculation_ids_to_outputs]

    return results_list


def get_state_improvements(exploration_id, exploration_version):
    """Returns a list of dicts, each representing a suggestion for improvement
    to a particular state.
    """
    ranked_states = []

    exploration = exp_services.get_exploration_by_id(exploration_id)
    state_names = exploration.states.keys()

    default_rule_answer_logs = stats_domain.StateRuleAnswerLog.get_multi(
        exploration_id, [{
            'state_name': state_name,
            'rule_str': exp_domain.DEFAULT_RULESPEC_STR
        } for state_name in state_names])

    statistics = stats_jobs.StatisticsAggregator.get_statistics(
        exploration_id, exploration_version)
    state_hit_counts = statistics['state_hit_counts']

    for ind, state_name in enumerate(state_names):
        total_entry_count = 0
        no_answer_submitted_count = 0
        if state_name in state_hit_counts:
            total_entry_count = (
                state_hit_counts[state_name]['total_entry_count'])
            no_answer_submitted_count = state_hit_counts[state_name].get(
                'no_answer_count', 0)

        if total_entry_count == 0:
            continue

        threshold = 0.2 * total_entry_count
        default_rule_answer_log = default_rule_answer_logs[ind]
        default_count = default_rule_answer_log.total_answer_count

        eligible_flags = []
        state = exploration.states[state_name]
        if (default_count > threshold and
                state.interaction.default_outcome is not None and
                state.interaction.default_outcome.dest == state_name):
            eligible_flags.append({
                'rank': default_count,
                'improve_type': IMPROVE_TYPE_DEFAULT})
        if no_answer_submitted_count > threshold:
            eligible_flags.append({
                'rank': no_answer_submitted_count,
                'improve_type': IMPROVE_TYPE_INCOMPLETE})

        if eligible_flags:
            eligible_flags = sorted(
                eligible_flags, key=lambda flag: flag['rank'], reverse=True)
            ranked_states.append({
                'rank': eligible_flags[0]['rank'],
                'state_name': state_name,
                'type': eligible_flags[0]['improve_type'],
            })

    return sorted(
        [state for state in ranked_states if state['rank'] != 0],
        key=lambda x: -x['rank'])


def get_versions_for_exploration_stats(exploration_id):
    """Returns list of versions for this exploration."""
    return stats_models.ExplorationAnnotationsModel.get_versions(
        exploration_id)


def get_exploration_stats(exploration_id, exploration_version):
    """Returns a dict with state statistics for the given exploration id.

    Note that exploration_version should be a string.
    """
    exploration = exp_services.get_exploration_by_id(exploration_id)
    exp_stats = stats_jobs.StatisticsAggregator.get_statistics(
        exploration_id, exploration_version)

    last_updated = exp_stats['last_updated']
    state_hit_counts = exp_stats['state_hit_counts']

    return {
        'improvements': get_state_improvements(
             exploration_id, exploration_version),
        'last_updated': last_updated,
        'num_completions': exp_stats['complete_exploration_count'],
        'num_starts': exp_stats['start_exploration_count'],
        'state_stats': {
            state_name: {
                'name': state_name,
                'firstEntryCount': (
                    state_hit_counts[state_name]['first_entry_count']
                    if state_name in state_hit_counts else 0),
                'totalEntryCount': (
                    state_hit_counts[state_name]['total_entry_count']
                    if state_name in state_hit_counts else 0),
            } for state_name in exploration.states
        },
    }


def record_answer(exploration_id, exploration_version, state_name,
                  handler_name, rule_str, session_id, time_spent_in_sec,
                  params, answer_value):
    """Record an answer by storing it to the corresponding StateAnswers entity.
    """
    # Retrieve state_answers from storage
    state_answers = get_state_answers(
        exploration_id, exploration_version, state_name)

    # Get interaction id from state_answers if it is stored there or
    # obtain it from the exploration (note that if the interaction id
    # of a state is changed by editing the exploration then this will
    # correspond to a new version of the exploration, for which a new
    # state_answers entity with correct updated interaction_id will
    # be created when the first answer is recorded).
    # If no interaction id exists, use None as placeholder.
    interaction_id = state_answers.interaction_id if state_answers else None

    if not interaction_id:
        # retrieve exploration and read its interaction id
        exploration = exp_services.get_exploration_by_id(
            exploration_id, version=exploration_version)
        interaction_id = exploration.states[state_name].interaction.id

    # Construct answer_dict and validate it
    answer_dict = {'answer_value': answer_value,
                   'time_spent_in_sec': time_spent_in_sec,
                   'rule_str': rule_str,
                   'session_id': session_id,
                   'handler_name': handler_name,
                   'interaction_id': interaction_id,
                   'params': params}
    _validate_answer(answer_dict)

    # Add answer to state_answers and commit to storage
    if state_answers:
        state_answers.answers_list.append(answer_dict)
    else:
        state_answers = stats_domain.StateAnswers(
            exploration_id, exploration_version,
            state_name, interaction_id, [answer_dict])
    _save_state_answers(state_answers)


def _save_state_answers(state_answers):
    """Validate StateAnswers domain object and commit to storage."""

    state_answers.validate()
    state_answers_model = stats_models.StateAnswersModel.create_or_update(
        state_answers.exploration_id, state_answers.exploration_version,
        state_answers.state_name, state_answers.interaction_id,
        state_answers.answers_list)
    state_answers_model.save()


def get_state_answers(exploration_id, exploration_version, state_name):
    """Get state answers domain object obtained from StateAnswersModel instance
    stored in data store.
    """
    state_answers_model = stats_models.StateAnswersModel.get_model(
        exploration_id, exploration_version, state_name)
    if state_answers_model:
        return stats_domain.StateAnswers(
            exploration_id, exploration_version, state_name,
            state_answers_model.interaction_id,
            state_answers_model.answers_list)
    else:
        return None


def _validate_answer(answer_dict):
    """Validate answer dicts. In particular, check the following:

    - Minimum set of keys: 'answer_value', 'time_spent_in_sec',
            'session_id'
    - Check size of every answer_value
    - Check time_spent_in_sec is non-negative
    """

    # TODO(msl): These validation methods need tests to ensure that
    # the right errors show up in the various cases.

    # Minimum set of keys required for answer_dicts in answers_list
    REQUIRED_ANSWER_DICT_KEYS = ['answer_value', 'time_spent_in_sec',
                                 'session_id']

    # There is a danger of data overflow if the answer log exceeds
    # 1 MB. Given 1000-5000 answers, each answer must be at most
    # 200-1000 bytes in size. We will address this later if it
    # happens regularly. At the moment, a ValidationError is raised if
    # an answer exceeds the maximum size.
    MAX_BYTES_PER_ANSWER_VALUE = 500

    # Prefix of strings that are cropped because they are too long.
    CROPPED_PREFIX_STRING = 'CROPPED: '
    # Answer value that is stored if non-string answer is too big
    PLACEHOLDER_FOR_TOO_LARGE_NONSTRING = 'TOO LARGE NONSTRING'

    # check type is dict
    if not isinstance(answer_dict, dict):
        raise utils.ValidationError(
            'Expected answer_dict to be a dict, received %s' %
            answer_dict)

    # check keys
    required_keys = set(REQUIRED_ANSWER_DICT_KEYS)
    actual_keys = set(answer_dict.keys())
    if not required_keys.issubset(actual_keys):
        missing_keys = required_keys.difference(actual_keys)
        raise utils.ValidationError(
            'answer_dict is missing required keys %s' % missing_keys)

    # check entries of answer_dict
    if (sys.getsizeof(answer_dict['answer_value']) >
            MAX_BYTES_PER_ANSWER_VALUE):

        if type(answer_dict['answer_value']) == str:
            logging.warning(
                'answer_value is too big to be stored: %s ...' %
            str(answer_dict['answer_value'][:MAX_BYTES_PER_ANSWER_VALUE]))
            answer_dict['answer_value'] = (
            '%s%s ...' %
            (CROPPED_PREFIX_STRING,
            str(answer_dict['answer_value'][:MAX_BYTES_PER_ANSWER_VALUE])))
        else:
            logging.warning('answer_value is too big to be stored')
            answer_dict['answer_value'] = PLACEHOLDER_FOR_TOO_LARGE_NONSTRING

    if not isinstance(answer_dict['session_id'], basestring):
        raise utils.ValidationError(
            'Expected session_id to be a string, received %s' %
            str(answer_dict['session_id']))

    if not isinstance(answer_dict['time_spent_in_sec'], float):
        raise utils.ValidationError(
            'Expected time_spent_in_sec to be a float, received %s' %
            str(answer_dict['time_spent_in_sec']))

    if answer_dict['time_spent_in_sec'] < 0.:
        raise utils.ValidationError(
            'Expected time_spent_in_sec to be non-negative, received %f' %
            answer_dict['time_spent_in_sec'])

