class lol.core.clans.GgListCommand
{
   var _data;
   var _dates;
   var _names;
   var _perms;
   var _posts;
   var _res;
   var _stats;
   function GgListCommand(resObj)
   {
      this._res = resObj.res;
      this._data = resObj.data;
      this._names = resObj.names;
      this._posts = resObj.posts;
      this._dates = resObj.dates;
      this._perms = resObj.perms;
      this._stats = resObj.stats;
   }
   function get res()
   {
      return this._res;
   }
   function get data()
   {
      return this._data;
   }
   function get names()
   {
      return this._names;
   }
   function get posts()
   {
      return this._posts;
   }
   function get dates()
   {
      return this._dates;
   }
   function get perms()
   {
      return this._perms;
   }
   function get stats()
   {
      return this._stats;
   }
}
