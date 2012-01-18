package org.openclinica.uconn;

import java.util.Collections;
import java.util.List;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.provider.BaseColumns;
import android.util.Log;

public class ContextProvider extends ContentProvider {
	
	public static final String AUTHORITY = "org.dimagi.uconn.screening";
	public static final Uri CONTEXT_BASE_URI = Uri.parse("content://" + AUTHORITY + "/context");
	
	@Override
	public String getType(Uri uri) {
		return null;  //i don't think this method is needed
	}

	@Override
	public Cursor query(Uri uri, String[] projection, String selection, String[] selectionArgs, String sortOrder) {
		List<String> pathSegs = uri.getPathSegments();
		String key = pathSegs.get(pathSegs.size() - 1);
		Object value = getValue(key);
		String type = typeFromValue(value);
		if (value instanceof Boolean) {
			value = ((Boolean)value ? 1 : 0);
		}
		
		MatrixCursor c = new MatrixCursor(new String[] {BaseColumns._ID, "value", "type"});
		c.newRow().add(key).add(value).add(type);
		
        return c;
	}

	protected Object getValue(String key) {
		if (key.equals("patid-mode")) {
			return "dbl-entry";
		} else if (key.equals("lookup-only")) {
			return true;
		} else {
			return null;
		}
	}
	
	static protected String typeFromValue(Object value) {
		if (value instanceof String) {
			return "str";
		} else if (value instanceof Integer) {
			return "int";
		} else if (value instanceof Boolean) {
			return "bool";
		} else {
			throw new IllegalArgumentException();
		}
	}
	
	@Override
	public boolean onCreate() {
		return true;
	}

	@Override
	public int delete(Uri uri, String selection, String[] selectionArgs) {
		throw new UnsupportedOperationException();
	}

	@Override
	public Uri insert(Uri uri, ContentValues values) {
		throw new UnsupportedOperationException();
	}

	@Override
	public int update(Uri uri, ContentValues values, String selection,
			String[] selectionArgs) {
		throw new UnsupportedOperationException();
	}

}
