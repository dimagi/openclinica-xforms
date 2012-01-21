package org.openclinica.uconn;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebView;
import android.widget.Toast;

public class ResultsActivity extends Activity {
	
	WebView web;
	
	public void onCreate(Bundle savedInstanceState) {
	    super.onCreate(savedInstanceState);
	    setContentView(R.layout.results);

	    String url = getIntent().getExtras().getString("url");
	    
	    web = (WebView) findViewById(R.id.webview);
	    web.getSettings().setJavaScriptEnabled(true);
	    web.loadUrl(url);
	    
		Toast toast = Toast.makeText(this, "I loaded " + url, Toast.LENGTH_LONG);
		toast.show();
	}
}
