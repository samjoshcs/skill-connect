"""
Matching logic for SkillConnect.

Kept in its own file (separate from routes.py) so it's easy to find and
explain on its own — this is the one function that does the "smart" part
of the app, everything else is just standard CRUD.
"""

from models import User, UserSkill


def find_matches(current_user_id):
    """
    Returns two lists of users:
      - mutual:  users who can teach something the current user wants to
                 learn, AND want to learn something the current user can teach.
                 (a true two-way skill swap)
      - partial: users who can teach something the current user wants to
                 learn, but it's not a two-way match.

    Mutual matches are considered a better fit, so they're shown first.
    """
    my_teach_skills = {s.skill_name.lower() for s in UserSkill.query.filter_by(
        user_id=current_user_id, type="can_teach").all()}
    my_learn_skills = {s.skill_name.lower() for s in UserSkill.query.filter_by(
        user_id=current_user_id, type="wants_to_learn").all()}

    mutual = []
    partial = []

    other_users = User.query.filter(User.id != current_user_id).all()

    for user in other_users:
        their_teach = {s.skill_name.lower() for s in user.can_teach_skills()}
        their_learn = {s.skill_name.lower() for s in user.wants_to_learn_skills()}

        if not their_teach:
            continue  # they haven't listed anything they can teach — skip them

        # Do they teach something I want to learn?
        teaches_what_i_want = bool(their_teach & my_learn_skills)

        if not teaches_what_i_want:
            continue  # not relevant to me at all

        # Do they ALSO want to learn something I can teach? -> mutual match
        wants_what_i_teach = bool(their_learn & my_teach_skills)

        if wants_what_i_teach:
            mutual.append(user)
        else:
            partial.append(user)

    return mutual, partial
