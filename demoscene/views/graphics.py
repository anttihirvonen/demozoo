from demoscene.shortcuts import *
from demoscene.models import Production, Byline
from demoscene.forms.production import *

from demoscene.views.productions import apply_order


from django.contrib.auth.decorators import login_required
from django.utils import simplejson as json
import datetime
from read_only_mode import writeable_site_required

from comments.models import ProductionComment
from comments.forms import ProductionCommentForm


def index(request):
	queryset = Production.objects.filter(supertype='graphics')

	order = request.GET.get('order', 'date')
	asc = request.GET.get('dir', 'desc') == 'asc'

	queryset = apply_order(queryset, order, asc)

	form = GraphicsIndexFilterForm(request.GET)

	if form.is_valid():
		if form.cleaned_data['platform']:
			queryset = queryset.filter(platforms=form.cleaned_data['platform'])
		if form.cleaned_data['production_type']:
			prod_types = ProductionType.get_tree(form.cleaned_data['production_type'])
			queryset = queryset.filter(types__in=prod_types)

	queryset = queryset.select_related('default_screenshot').prefetch_related('author_nicks__releaser', 'author_affiliation_nicks__releaser', 'platforms', 'types')

	production_page = get_page(
		queryset,
		request.GET.get('page', '1'))

	return render(request, 'graphics/index.html', {
		'order': order,
		'production_page': production_page,
		'menu_section': "graphics",
		'asc': asc,
		'form': form,
	})


def show(request, production_id, edit_mode=False):
	production = get_object_or_404(Production, id=production_id)
	if production.supertype != 'graphics':
		return HttpResponseRedirect(production.get_absolute_url())

	screenshots = production.screenshots.order_by('id')
	screenshots_json = json.dumps([
		{
			'original_url': pic.original_url, 'src': pic.standard_url,
			'width': pic.standard_width, 'height': pic.standard_height
		}
		for pic in screenshots
	])

	if request.user.is_authenticated():
		comment = ProductionComment(production=production, user=request.user)
		comment_form = ProductionCommentForm(instance=comment, prefix="comment")
		tags_form = ProductionTagsForm(instance=production)
	else:
		comment_form = None
		tags_form = None

	return render(request, 'productions/show.html', {
		'production': production,
		'credits': production.credits.order_by('nick__name', 'category'),
		'screenshots': screenshots,
		'screenshots_json': screenshots_json,
		'download_links': production.links.filter(is_download_link=True),
		'external_links': production.links.filter(is_download_link=False),
		'competition_placings': production.competition_placings.order_by('competition__party__start_date_date'),
		'invitation_parties': production.invitation_parties.order_by('start_date_date'),
		'tags': production.tags.order_by('name'),
		'blurbs': production.blurbs.all() if request.user.is_staff else None,
		'comment_form': comment_form,
		'tags_form': tags_form,
	})


def history(request, production_id):
	production = get_object_or_404(Production, id=production_id)
	if production.supertype != 'graphics':
		return HttpResponseRedirect(production.get_history_url())
	return render(request, 'productions/history.html', {
		'production': production,
		'edits': Edit.for_model(production, request.user.is_staff),
	})


@writeable_site_required
@login_required
def create(request):
	if request.method == 'POST':
		production = Production(updated_at=datetime.datetime.now())
		form = CreateGraphicsForm(request.POST, instance=production)
		download_link_formset = ProductionDownloadLinkFormSet(request.POST, instance=production)
		if form.is_valid() and download_link_formset.is_valid():
			form.save()
			download_link_formset.save()
			form.log_creation(request.user)
			return HttpResponseRedirect(production.get_absolute_url())
	else:
		form = CreateGraphicsForm(initial={
			'byline': Byline.from_releaser_id(request.GET.get('releaser_id'))
		})
		download_link_formset = ProductionDownloadLinkFormSet()
	return render(request, 'graphics/create.html', {
		'form': form,
		'download_link_formset': download_link_formset,
	})
