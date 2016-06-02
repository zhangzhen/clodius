#!/usr/bin/python

from time import gmtime, strftime
import argparse

import clodius.fpark as cfp
import clodius.tiles as cti
import clodius.describe_dataset as cdd
import clodius.save_tiles as cst

import fpark
import functools as ft

import json
import os.path as op
import sys
import time

def main():
    usage = """
    python make_tiles.py input_file

    Create tiles for all of the entries in the JSON file.
    """
    num_args= 1
    parser = argparse.ArgumentParser()

    #parser.add_argument('-o', '--options', dest='some_option', default='yo', help="Place holder for a real option", type='str')
    #parser.add_argument('-u', '--useless', dest='uselesss', default=False, action='store_true', help='Another useless option')
    parser.add_argument('input_file')
    parser.add_argument('-b', '--bins-per-dimension', 
                        help='The number of bins to divide the data into',
                        default=1,
                        type=int)
    parser.add_argument('--use-spark', default=False, action='store_true',
                        help='Use spark to distribute the workload')

    parser.add_argument('-r', '--resolution', 
                        help='The resolution of the data (applies only to matrix data)',
                        type=int)

    parser.add_argument('--importance', action='store_true', help='Create tiles by importance') 

    parser.add_argument('-i', '--importance-field', dest='importance_field', default='importance_field',
            help='The field in each JSON entry that indicates how important that entry is',
            type=str)
    parser.add_argument('-v', '--value', dest='value_field', default='count',
            help='The that has the value of each point. Used for aggregation and display')

    group = parser.add_mutually_exclusive_group()

    group.add_argument('-p', '--position', dest='position', default='position',
            help='Where this entry would be placed on the x axis',
            type=str)
    group.add_argument('-s', '--sort-by', 
            default=None,
            help='Sort by a field and use as the position') 

    parser.add_argument('--end-position', default=None,
                        help = "Use a field to indicate the end of a particular element so that it appears in all tiles that intersect it")
    parser.add_argument('-e', '--max-entries-per-tile', dest='max_entries_per_tile', default=15,
        help='The maximum number of entries that can be displayed on a single tile',
        type=int)
    parser.add_argument('-c', '--column-names', dest='column_names', default=None)
    parser.add_argument('-m', '--max-zoom', dest='max_zoom', 
            help='The maximum zoom level', type=int, required=True)
    parser.add_argument('--min-pos', dest='min_pos', default=None,
            help='The minimum x position', type=float)
    parser.add_argument('--max-pos', dest='max_pos', default=None,
            help='The maximum x position', type=float)
    parser.add_argument('--min-value', 
            help='The field which will be used to determinethe minimum value for any data point', 
            default='min_y')
    parser.add_argument('--max-value', 
            help='The field which will be used to determine the maximum value for any data point', 
            default='max_y')
    parser.add_argument('--range',
            help="Use two columns to create a range (i.e. pos1,pos2",
            default=None)
    parser.add_argument('--range-except-0',
            help="Don't expand rows which have values less than 0",
            default=None)
    parser.add_argument('--gzip', help='Compress the output JSON files using gzip', 
            action='store_true')
    parser.add_argument('--output-format', 
            help='The format for the output matrix, can be either "dense" or "sparse"',
            default='sparse')
    parser.add_argument('--add-uuid',
            help='Add a uuid to each element',
            action='store_true',
            default=False)
    parser.add_argument('--reverse-importance',
            help='Reverse the ordering of the importance',
            action='store_true',
            default=False)

    output_group = parser.add_mutually_exclusive_group(required=True)

    output_group.add_argument('--elasticsearch-path',
            help='Send the output to an elasticsearch instance',
            default=None)
    output_group.add_argument('-o', '--output-dir', help='The directory to place the tiles',
            default=None)
    
    parser.add_argument('--delimiter',
            help="The delimiter separating the different columns in the input files",
            default=None)

    parser.add_argument('--elasticsearch-nodes', 
            help='Specify elasticsearch nodes to push the completions to',
            default=None)
    parser.add_argument('--elasticsearch-index',
            help="The index to place the results in",
            default='test')
    parser.add_argument('--elasticsearch-doctype',
            help="The type of document to index",
            default="autocomplete")

    args = parser.parse_args()

    if not args.importance:
        if args.output_format not in ['sparse', 'dense']:
            print >>sys.stderr, 'ERROR: The output format must be one of "dense" or "sparse"'

    dim_names = args.position.split(',')

    sc = None

    if args.use_spark:
        from pyspark import SparkContext
        sc = SparkContext()
    else:
        sys.stderr.write("setting sc:")
        sc = cfp.FakeSparkContext

    if args.column_names is not None:
        args.column_names = args.column_names.split(',')

    print "start time:", strftime("%Y-%m-%d %H:%M:%S", gmtime())
    entries = cti.load_entries_from_file(sc, args.input_file, args.column_names,
            delimiter=args.delimiter,
            elasticsearch_path=args.elasticsearch_path)
    print "load entries time:", strftime("%Y-%m-%d %H:%M:%S", gmtime())

    if args.range is not None:
        # if a pair of columns specifies a range of values, then create multiple
        # entries for each value within that range (e.g. bed files)
        range_cols = args.range.split(',')
        entries = entries.flatMap(lambda x: cti.expand_range(x, *range_cols, range_except_0 = args.range_except_0))

    if args.importance:
        # Data will be aggregated by importance. Only more "important" pieces of information will
        # be passed onto the lower resolution tiles if they are too crowded
        tileset = cti.make_tiles_by_importance(sc, entries, dim_names=args.position.split(','), 
                end_dim_names = args.end_position.split(','),
                max_zoom=args.max_zoom, 
                importance_field=args.importance_field,
                output_dir=args.output_dir,
                max_entries_per_tile = args.max_entries_per_tile,
                gzip_output=args.gzip, add_uuid=args.add_uuid,
                reverse_importance=args.reverse_importance)
    else:
        # Data will be aggregated by binning. This means that it two adjacent bins should be able
        # to be reduced into one using some function (i.e. 'sum', 'min', 'max')
        tileset = cti.make_tiles_by_binning(sc, entries, args.position.split(','), 
                args.max_zoom, args.value_field, args.importance_field,
                bins_per_dimension=args.bins_per_dimension,
                resolution=args.resolution)

    all_tiles = tileset['tiles']

    if args.elasticsearch_nodes is not None:
        # save the tiles to an elasticsearch database
        save_tile_to_elasticsearch = ft.partial(cst.save_tile_to_elasticsearch,
            elasticsearch_nodes = args.elasticsearch_nodes,
            elasticsearch_path = args.elasticsearch_path)

        all_tiles.foreachPartition(save_tile_to_elasticsearch)

        tileset_info_rdd = sc.parallelize([{"tile_value": tileset['tileset_info'], 
                                            "tile_id": "tileset_info"}])
        tileset_info_rdd.foreachPartition(save_tile_to_elasticsearch)

        histogram_rdd = sc.parallelize([{"tile_value": tileset_info['histogram'], 
                                         "tile_id": "histogram"}])

        histogram_rdd.foreachPartition(save_tile_to_elasticsearch)
    else:
        # dump tiles to a directory structure
        all_tiles.foreach(ft.partial(cst.save_tile,
                                     output_dir=args.output_dir, 
                                     gzip_output=args.gzip))

        dataset_info = cdd.describe_dataset(sys.argv, args)

        with open(op.join(args.output_dir, 'dataset_info.json'), 'w') as f:
            json.dump(dataset_info, f, indent=2)

        with open(op.join(args.output_dir, 'tile_info.json'), 'w') as f:
            json.dump(tileset['tileset_info'], f, indent=2)

        if 'histogram' in tileset:
            with open(op.join(args.output_dir, 'value_histogram.json'), 'w') as f:
                json.dump(tileset['histogram'], f, indent=2)


if __name__ == '__main__':
    main()


