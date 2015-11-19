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

__author__ = 'Jeremy Emerson'

from core.domain import event_services
from core.domain import exp_domain
from core.domain import exp_services
from core.domain import rule_domain
from core.domain import stats_domain
from core.domain import stats_jobs
from core.domain import stats_services
from core.tests import test_utils
import feconf


class ModifiedStatisticsAggregator(stats_jobs.StatisticsAggregator):
    """A modified StatisticsAggregator that does not start a new batch
    job when the previous one has finished.
    """
    @classmethod
    def _get_batch_job_manager_class(cls):
        return ModifiedStatisticsMRJobManager

    @classmethod
    def _kickoff_batch_job_after_previous_one_ends(cls):
        pass


class ModifiedStatisticsMRJobManager(stats_jobs.StatisticsMRJobManager):

    @classmethod
    def _get_continuous_computation_class(cls):
        return ModifiedStatisticsAggregator


class AnalyticsEventHandlersUnitTests(test_utils.GenericTestBase):
    """Test the event handlers for analytics events."""

    DEFAULT_RULESPEC_STR = exp_domain.DEFAULT_RULESPEC_STR
    DEFAULT_SESSION_ID = 'session_id'
    DEFAULT_TIME_SPENT = 5.0
    DEFAULT_PARAMS = {}

    def test_record_answer_submitted(self):
        exp = exp_domain.Exploration.create_default_exploration(
            'eid', 'A title', 'A category')
        exp_services.save_new_exploration('fake@user.com', exp)
        state_name = exp.init_state_name

        event_services.AnswerSubmissionEventHandler.record(
            'eid', 1, state_name, 'submit',
            self.DEFAULT_RULESPEC_STR, self.DEFAULT_SESSION_ID,
            self.DEFAULT_TIME_SPENT, self.DEFAULT_PARAMS, 'answer')

        answer_log = stats_domain.StateRuleAnswerLog.get(
            'eid', state_name, self.DEFAULT_RULESPEC_STR)
        self.assertEquals(answer_log.answers, {'answer': 1})

        event_services.AnswerSubmissionEventHandler.record(
            'eid', 1, state_name, 'submit',
            self.DEFAULT_RULESPEC_STR, self.DEFAULT_SESSION_ID,
            self.DEFAULT_TIME_SPENT, self.DEFAULT_PARAMS, 'answer')

        answer_log = stats_domain.StateRuleAnswerLog.get(
            'eid', state_name, self.DEFAULT_RULESPEC_STR)
        self.assertEquals(answer_log.answers, {'answer': 2})

        answer_log = stats_domain.StateRuleAnswerLog.get(
            'eid', state_name, self.DEFAULT_RULESPEC_STR)
        self.assertEquals(answer_log.answers, {'answer': 2})

    def test_resolve_answers_for_default_rule(self):
        exp = exp_domain.Exploration.create_default_exploration(
        'eid', 'A title', 'A category')
        exp_services.save_new_exploration('fake@user.com', exp)
        state_name = exp.init_state_name

        # Submit three answers.
        event_services.AnswerSubmissionEventHandler.record(
            'eid', 1, state_name, 'submit',
            self.DEFAULT_RULESPEC_STR, self.DEFAULT_SESSION_ID,
            self.DEFAULT_TIME_SPENT, self.DEFAULT_PARAMS, 'a1')
        event_services.AnswerSubmissionEventHandler.record(
            'eid', 1, state_name, 'submit',
            self.DEFAULT_RULESPEC_STR, self.DEFAULT_SESSION_ID,
            self.DEFAULT_TIME_SPENT, self.DEFAULT_PARAMS, 'a2')
        event_services.AnswerSubmissionEventHandler.record(
            'eid', 1, state_name, 'submit',
            self.DEFAULT_RULESPEC_STR, self.DEFAULT_SESSION_ID,
            self.DEFAULT_TIME_SPENT, self.DEFAULT_PARAMS, 'a3')

        answer_log = stats_domain.StateRuleAnswerLog.get(
            'eid', state_name, self.DEFAULT_RULESPEC_STR)
        self.assertEquals(
            answer_log.answers, {'a1': 1, 'a2': 1, 'a3': 1})

        # Nothing changes if you try to resolve an invalid answer.
        event_services.DefaultRuleAnswerResolutionEventHandler.record(
            'eid', state_name, ['fake_answer'])
        answer_log = stats_domain.StateRuleAnswerLog.get(
            'eid', state_name, self.DEFAULT_RULESPEC_STR)
        self.assertEquals(
            answer_log.answers, {'a1': 1, 'a2': 1, 'a3': 1})

        # Resolve two answers.
        event_services.DefaultRuleAnswerResolutionEventHandler.record(
            'eid', state_name, ['a1', 'a2'])

        answer_log = stats_domain.StateRuleAnswerLog.get(
            'eid', state_name, self.DEFAULT_RULESPEC_STR)
        self.assertEquals(answer_log.answers, {'a3': 1})

        # Nothing changes if you try to resolve an answer that has already
        # been resolved.
        event_services.DefaultRuleAnswerResolutionEventHandler.record(
            'eid', state_name, ['a1'])
        answer_log = stats_domain.StateRuleAnswerLog.get(
            'eid', state_name, self.DEFAULT_RULESPEC_STR)
        self.assertEquals(answer_log.answers, {'a3': 1})

        # Resolve the last answer.
        event_services.DefaultRuleAnswerResolutionEventHandler.record(
            'eid', state_name, ['a3'])

        answer_log = stats_domain.StateRuleAnswerLog.get(
            'eid', state_name, 'Rule')
        self.assertEquals(answer_log.answers, {})


class StateImprovementsUnitTests(test_utils.GenericTestBase):
    """Test the get_state_improvements() function."""

    DEFAULT_RULESPEC_STR = exp_domain.DEFAULT_RULESPEC_STR
    DEFAULT_SESSION_ID = 'session_id'
    DEFAULT_RULESPEC_STR = exp_domain.DEFAULT_RULESPEC_STR
    DEFAULT_TIME_SPENT = 5.0
    DEFAULT_PARAMS = {}

    def test_get_state_improvements(self):
        exp = exp_domain.Exploration.create_default_exploration(
            'eid', 'A title', 'A category')
        exp_services.save_new_exploration('fake@user.com', exp)

        for ind in range(5):
            event_services.StartExplorationEventHandler.record(
                'eid', 1, exp.init_state_name, 'session_id_%s' % ind,
                {}, feconf.PLAY_TYPE_NORMAL)
            event_services.StateHitEventHandler.record(
                'eid', 1, exp.init_state_name, 'session_id_%s' % ind,
                {}, feconf.PLAY_TYPE_NORMAL)
        event_services.AnswerSubmissionEventHandler.record(
            'eid', 1, exp.init_state_name, 'submit',
            self.DEFAULT_RULESPEC_STR, self.DEFAULT_SESSION_ID,
            self.DEFAULT_TIME_SPENT, self.DEFAULT_PARAMS, '1')
        for _ in range(2):
            event_services.AnswerSubmissionEventHandler.record(
                'eid', 1, exp.init_state_name, 'submit',
                self.DEFAULT_RULESPEC_STR, self.DEFAULT_SESSION_ID,
                self.DEFAULT_TIME_SPENT, self.DEFAULT_PARAMS, '2')
        ModifiedStatisticsAggregator.start_computation()
        self.process_and_flush_pending_tasks()
        with self.swap(stats_jobs.StatisticsAggregator, 'get_statistics',
                       ModifiedStatisticsAggregator.get_statistics):
            self.assertEquals(
                stats_services.get_state_improvements('eid', 1), [{
                    'type': 'default',
                    'rank': 3,
                    'state_name': exp.init_state_name
                }])

    def test_single_default_rule_hit(self):
        exp = exp_domain.Exploration.create_default_exploration(
            'eid', 'A title', 'A category')
        exp_services.save_new_exploration('fake@user.com', exp)
        state_name = exp.init_state_name

        event_services.StartExplorationEventHandler.record(
            'eid', 1, state_name, 'session_id', {}, feconf.PLAY_TYPE_NORMAL)
        event_services.StateHitEventHandler.record(
            'eid', 1, state_name, 'session_id', {},
            feconf.PLAY_TYPE_NORMAL)
        event_services.AnswerSubmissionEventHandler.record(
            'eid', 1, state_name, 'submit',
            self.DEFAULT_RULESPEC_STR, 'session_id', self.DEFAULT_TIME_SPENT,
            self.DEFAULT_PARAMS, '1')
        ModifiedStatisticsAggregator.start_computation()
        self.process_and_flush_pending_tasks()
        with self.swap(stats_jobs.StatisticsAggregator, 'get_statistics',
                       ModifiedStatisticsAggregator.get_statistics):
            self.assertEquals(
                stats_services.get_state_improvements('eid', 1), [{
                    'type': 'default',
                    'rank': 1,
                    'state_name': exp.init_state_name
                }])

    def test_no_improvement_flag_hit(self):
        self.save_new_valid_exploration(
            'eid', 'fake@user.com', end_state_name='End')
        exp = exp_services.get_exploration_by_id('eid')

        not_default_rule_spec = exp_domain.RuleSpec('Equals', {'x': 'Text'})
        not_default_rule_spec_str = (
            not_default_rule_spec.stringify_classified_rule())
        init_interaction = exp.init_state.interaction
        init_interaction.answer_groups.append(exp_domain.AnswerGroup(
            exp_domain.Outcome(exp.init_state_name, [], {}),
            [not_default_rule_spec]))
        init_interaction.default_outcome = exp_domain.Outcome(
            'End', [], {})
        exp_services._save_exploration('fake@user.com', exp, '', [])

        event_services.AnswerSubmissionEventHandler.record(
            'eid', 1, exp.init_state_name, 'submit',
            not_default_rule_spec_str, self.DEFAULT_SESSION_ID,
            self.DEFAULT_TIME_SPENT, self.DEFAULT_PARAMS, '1')
        self.assertEquals(stats_services.get_state_improvements('eid', 1), [])

    def test_incomplete_and_default_flags(self):
        exp = exp_domain.Exploration.create_default_exploration(
            'eid', 'A title', 'A category')
        exp_services.save_new_exploration('fake@user.com', exp)
        state_name = exp.init_state_name

        # Fail to answer twice.
        for i in range(2):
            event_services.StartExplorationEventHandler.record(
                'eid', 1, state_name, 'session_id %d' % i, {},
                feconf.PLAY_TYPE_NORMAL)
            event_services.StateHitEventHandler.record(
                'eid', 1, state_name, 'session_id %d' % i,
                {}, feconf.PLAY_TYPE_NORMAL)
            event_services.MaybeLeaveExplorationEventHandler.record(
                'eid', 1, state_name, 'session_id %d' % i, 10.0, {},
                feconf.PLAY_TYPE_NORMAL)

        # Hit the default rule once.
        event_services.StateHitEventHandler.record(
            'eid', 1, state_name, 'session_id 3', {}, feconf.PLAY_TYPE_NORMAL)
        event_services.AnswerSubmissionEventHandler.record(
            'eid', 1, state_name, 'submit',
            self.DEFAULT_RULESPEC_STR, 'session_id 3',
            self.DEFAULT_TIME_SPENT, self.DEFAULT_PARAMS, '1')

        # The result should be classified as incomplete.
        ModifiedStatisticsAggregator.start_computation()
        self.process_and_flush_pending_tasks()
        with self.swap(stats_jobs.StatisticsAggregator, 'get_statistics',
                       ModifiedStatisticsAggregator.get_statistics):
            self.assertEquals(
                stats_services.get_state_improvements('eid', 1), [{
                    'rank': 2,
                    'type': 'incomplete',
                    'state_name': state_name
                }])

        # Now hit the default two more times. The result should be classified
        # as default.
        for i in range(2):
            event_services.StateHitEventHandler.record(
                'eid', 1, state_name, 'session_id',
                {}, feconf.PLAY_TYPE_NORMAL)
            event_services.AnswerSubmissionEventHandler.record(
                'eid', 1, state_name, 'submit',
                self.DEFAULT_RULESPEC_STR, 'session_id',
                self.DEFAULT_TIME_SPENT, self.DEFAULT_PARAMS, '1')
        with self.swap(stats_jobs.StatisticsAggregator, 'get_statistics',
                       ModifiedStatisticsAggregator.get_statistics):
            self.assertEquals(
                stats_services.get_state_improvements('eid', 1), [{
                    'rank': 3,
                    'type': 'default',
                    'state_name': state_name
                }])

    def test_two_state_default_hit(self):
        self.save_new_default_exploration('eid', 'fake@user.com')
        exp = exp_services.get_exploration_by_id('eid')

        FIRST_STATE_NAME = exp.init_state_name
        SECOND_STATE_NAME = 'State 2'
        exp_services.update_exploration('fake@user.com', 'eid', [{
            'cmd': 'edit_state_property',
            'state_name': FIRST_STATE_NAME,
            'property_name': 'widget_id',
            'new_value': 'TextInput',
        }, {
            'cmd': 'add_state',
            'state_name': SECOND_STATE_NAME,
        }, {
            'cmd': 'edit_state_property',
            'state_name': SECOND_STATE_NAME,
            'property_name': 'widget_id',
            'new_value': 'TextInput',
        }], 'Add new state')

        # Hit the default rule of state 1 once, and the default rule of state 2
        # twice. Note that both rules are self-loops.
        event_services.StartExplorationEventHandler.record(
            'eid', 2, FIRST_STATE_NAME, 'session_id', {},
            feconf.PLAY_TYPE_NORMAL)
        event_services.StateHitEventHandler.record(
            'eid', 2, FIRST_STATE_NAME, 'session_id',
            {}, feconf.PLAY_TYPE_NORMAL)
        event_services.AnswerSubmissionEventHandler.record(
            'eid', 2, FIRST_STATE_NAME, 'submit',
            self.DEFAULT_RULESPEC_STR, 'session_id',
            self.DEFAULT_TIME_SPENT, self.DEFAULT_PARAMS, '1')

        for i in range(2):
            event_services.StateHitEventHandler.record(
                'eid', 2, SECOND_STATE_NAME, 'session_id',
                {}, feconf.PLAY_TYPE_NORMAL)
            event_services.AnswerSubmissionEventHandler.record(
                'eid', 2, SECOND_STATE_NAME, 'submit',
                self.DEFAULT_RULESPEC_STR, 'session_id',
                self.DEFAULT_TIME_SPENT, self.DEFAULT_PARAMS, '1')
        ModifiedStatisticsAggregator.start_computation()
        self.process_and_flush_pending_tasks()
        with self.swap(stats_jobs.StatisticsAggregator, 'get_statistics',
                       ModifiedStatisticsAggregator.get_statistics):
            states = stats_services.get_state_improvements('eid', 2)
        self.assertEquals(states, [{
            'rank': 2,
            'type': 'default',
            'state_name': SECOND_STATE_NAME
        }, {
            'rank': 1,
            'type': 'default',
            'state_name': FIRST_STATE_NAME
        }])

        # Hit the default rule of state 1 two more times.
        for i in range(2):
            event_services.StateHitEventHandler.record(
                'eid', 1, FIRST_STATE_NAME, 'session_id',
                {}, feconf.PLAY_TYPE_NORMAL)
            event_services.AnswerSubmissionEventHandler.record(
                'eid', 1, FIRST_STATE_NAME, 'submit',
                self.DEFAULT_RULESPEC_STR, 'session_id',
                self.DEFAULT_TIME_SPENT, self.DEFAULT_PARAMS, '1')

        with self.swap(stats_jobs.StatisticsAggregator, 'get_statistics',
                       ModifiedStatisticsAggregator.get_statistics):
            states = stats_services.get_state_improvements('eid', 2)
        self.assertEquals(states, [{
            'rank': 3,
            'type': 'default',
            'state_name': FIRST_STATE_NAME
        }, {
            'rank': 2,
            'type': 'default',
            'state_name': SECOND_STATE_NAME
        }])


class UnresolvedAnswersTests(test_utils.GenericTestBase):
    """Test the unresolved answers methods."""

    DEFAULT_RULESPEC_STR = exp_domain.DEFAULT_RULESPEC_STR
    DEFAULT_SESSION_ID = 'session_id'
    DEFAULT_TIME_SPENT = 5.0
    DEFAULT_PARAMS = {}

    def test_get_top_unresolved_answers(self):
        exp = exp_domain.Exploration.create_default_exploration(
            'eid', 'title', 'category')
        exp_services.save_new_exploration('user_id', exp)
        state_name = exp.init_state_name

        self.assertEquals(
            stats_services.get_top_unresolved_answers_for_default_rule(
                'eid', state_name), {})

        event_services.AnswerSubmissionEventHandler.record(
            'eid', 1, state_name, 'submit',
            self.DEFAULT_RULESPEC_STR, 'session', self.DEFAULT_TIME_SPENT,
            self.DEFAULT_PARAMS, 'a1')
        self.assertEquals(
            stats_services.get_top_unresolved_answers_for_default_rule(
                'eid', state_name), {'a1': 1})

        event_services.AnswerSubmissionEventHandler.record(
            'eid', 1, state_name, 'submit',
            self.DEFAULT_RULESPEC_STR, 'session', self.DEFAULT_TIME_SPENT,
            self.DEFAULT_PARAMS, 'a1')
        self.assertEquals(
            stats_services.get_top_unresolved_answers_for_default_rule(
                'eid', state_name), {'a1': 2})

        event_services.DefaultRuleAnswerResolutionEventHandler.record(
            'eid', state_name, ['a1'])
        self.assertEquals(
            stats_services.get_top_unresolved_answers_for_default_rule(
                'eid', state_name), {})


class EventLogEntryTests(test_utils.GenericTestBase):
    """Test for the event log creation."""

    def test_create_events(self):
        """Basic test that makes sure there are no exceptions thrown."""
        event_services.StartExplorationEventHandler.record(
            'eid', 2, 'state', 'session', {}, feconf.PLAY_TYPE_NORMAL)
        event_services.MaybeLeaveExplorationEventHandler.record(
            'eid', 2, 'state', 'session', 27.2, {}, feconf.PLAY_TYPE_NORMAL)
